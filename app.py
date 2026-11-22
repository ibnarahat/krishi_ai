"""Krishi AI (no API key): FastAPI server for the rule-based multi-agent advisor."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from krishi.agents import (AGENTS, agent_season_month, agent_veg, calc, coordinate_chat,
                           coordinate_diagnose, coordinate_plan, now_dhaka)
from krishi.knowledge import MONTH_BN, SOIL_TYPES, SYMPTOMS, TO_DECIMAL, VEG, VEGETABLES, SEASONS

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Krishi AI", docs_url=None, redoc_url=None)


async def body(request: Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@app.get("/api/meta")
async def meta():
    return {
        "agents": [{"id": k, "bn": v[0], "en": v[1]} for k, v in AGENTS.items()],
        "crops": [{"id": v["id"], "bn": v["bn"], "seasons": v["seasons"], "sow": v["sow"], "rooftop": v["rooftop"]} for v in VEGETABLES],
        "symptoms": [{"group": g, "items": [{"id": i, "bn": t} for i, t in items]} for g, items in SYMPTOMS.items()],
        "seasons": {k: v["bn"] for k, v in SEASONS.items()},
        "months": MONTH_BN,
        "units": list(TO_DECIMAL),
        "soils": list(SOIL_TYPES),
        "month_now": now_dhaka().month,
    }


@app.post("/api/chat")
async def chat(request: Request):
    q = str((await body(request)).get("q", "")).strip()[:1000]
    if not q:
        raise HTTPException(400, "empty question")
    return coordinate_chat(q)


@app.post("/api/diagnose")
async def diagnose(request: Request):
    d = await body(request)
    tags = d.get("tags") if isinstance(d.get("tags"), list) else []
    info = d.get("info") if isinstance(d.get("info"), dict) else {}
    return coordinate_diagnose(str(d.get("crop", "")), [str(t) for t in tags][:30], str(d.get("spread", "")), info)


@app.post("/api/plan")
async def plan(request: Request):
    d = await body(request)
    return coordinate_plan({k: str(v)[:300] for k, v in d.items()})


@app.post("/api/calc")
async def cost(request: Request):
    d = await body(request)
    return calc({k: str(v)[:50] for k, v in d.items()})


@app.get("/api/crop/{crop_id}")
async def crop(crop_id: str):
    if crop_id not in VEG:
        raise HTTPException(404, "unknown crop")
    return {"answer": agent_veg(crop_id), "agents": ["coord", "veg", "season", "pest", "disease"]}


@app.get("/api/month/{m}")
async def month(m: int):
    if not 1 <= m <= 12:
        raise HTTPException(404, "bad month")
    return {"answer": agent_season_month(m), "agents": ["coord", "season", "veg"]}


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")
