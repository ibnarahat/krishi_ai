"""Krishi AI server (Python / FastAPI) using the Google Gemini API."""
import os
import re
import time
import base64
from collections import defaultdict, deque
from pathlib import Path

from google import genai
from google.genai import types
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
STATIC = BASE / "static"

MODELS = {
    "quick": os.getenv("MODEL_QUICK", "gemini-3.5-flash-lite"),
    "default": os.getenv("MODEL_DEFAULT", "gemini-3.8-flash"),
}
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4000"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "40"))
ACCESS_CODE = os.getenv("ACCESS_CODE", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY is missing. Add it in Render > Environment.")

# Let the web service start even if the key has not been configured yet.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
app = FastAPI(title="Krishi AI", docs_url=None, redoc_url=None)
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

    async def generate():
        if client is None:
            print("Gemini error: GEMINI_API_KEY is not configured.")
            yield "\n\n[[ERROR:bad_key]]"
            return

        try:
            contents = []
            for data_url in images[:4]:
                match = DATA_URL.match(data_url or "")
                if match:
                    mime_type = match.group(1)
                    image_bytes = base64.b64decode(match.group(2), validate=True)
                    contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            contents.append(types.Part.from_text(text=prompt))

            stream = await client.aio.models.generate_content_stream(
                model=MODELS.get(tier, MODELS["default"]),
                contents=contents,
                config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS),
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except Exception as exc:
            error_text = repr(exc)
            lowered = error_text.lower()
            print("Gemini error:", error_text)
            if any(term in lowered for term in ("429", "resource_exhausted", "rate limit")):
                yield "\n\n[[ERROR:rate_limited]]"
            elif any(term in lowered for term in ("401", "403", "api key", "unauthenticated", "permission denied")):
                yield "\n\n[[ERROR:bad_key]]"
            elif any(term in lowered for term in ("404", "not found", "model")):
                yield "\n\n[[ERROR:model]]"
            else:
                yield "\n\n[[ERROR:error]]"

    return StreamingResponse(
        generate(), media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")
