"""Krishi AI server (Python / FastAPI).

Serves the web app from ./static and forwards each agent call to the Anthropic API.
The API key stays on the server and is never sent to the browser.
"""
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path

import anthropic
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
STATIC = BASE / "static"

MODELS = {
    "quick": os.getenv("MODEL_QUICK", "claude-haiku-5-5"),
    "default": os.getenv("MODEL_DEFAULT", "claude-sonnet-5-5"),
}
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4000"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "40"))  # one question = about 4-9 calls
ACCESS_CODE = os.getenv("ACCESS_CODE", "")

if not os.getenv("ANTHROPIC_API_KEY"):
    print("ANTHROPIC_API_KEY is missing. Add it in Render > Environment.")

client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY
app = FastAPI(title="Krishi AI", docs_url=None, redoc_url=None)

# Simple in-memory rate limit per visitor IP (fine for a single Render instance).
_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def rate_limited(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp|gif));base64,(.+)$", re.S)


@app.get("/api/config")
async def config():
    return {"needsCode": bool(ACCESS_CODE), "images": True}


@app.post("/api/agent")
async def agent(request: Request):
    if ACCESS_CODE and request.headers.get("x-access-code") != ACCESS_CODE:
        return JSONResponse({"error": "not_granted"}, status_code=401)
    if rate_limited(client_ip(request)):
        return JSONResponse({"error": "rate_limited"}, status_code=429)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_request"}, status_code=400)

    prompt = body.get("prompt")
    tier = body.get("tier", "default")
    images = body.get("images") or []
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 60000:
        return JSONResponse({"error": "bad_request"}, status_code=400)

    content = []
    for url in images[:4]:
        m = DATA_URL.match(url or "")
        if m:
            content.append({"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}})
    content.append({"type": "text", "text": prompt})

    async def generate():
        try:
            async with client.messages.stream(
                model=MODELS.get(tier, MODELS["default"]),
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": content}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.AuthenticationError:
            print("Anthropic error: invalid API key")
            yield "\n\n[[ERROR:bad_key]]"
        except anthropic.RateLimitError:
            yield "\n\n[[ERROR:rate_limited]]"
        except Exception as e:  # network, overload, etc.
            print("Anthropic error:", repr(e))
            yield "\n\n[[ERROR:error]]"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")
