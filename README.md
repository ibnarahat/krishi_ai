# Krishi AI (কৃষি AI): no API key version

This is a Bengali farming advisor for Bangladesh. It runs entirely on its own built-in knowledge base, so it needs **no API key, no AI service, and nothing to pay for**. It works on Render's free plan.

## What it does

| Tab | What farmers do |
|---|---|
| **পরামর্শ** (chat) | Type a question in Bengali. The coordinator spots the crop, symptoms, month, or topic and sends it to the right agents. |
| **লক্ষণ দিয়ে রোগ নির্ণয়** | Pick a crop, then tick symptoms from 52 options. You get a ranked report: likely problem, alternatives, match %, severity, and what to do. |
| **চাষ পরিকল্পনা** | Fill in land, budget, soil, water, and season. You get crop scores, a schedule, a monthly calendar, risks, and a **cost & profit calculator**. |
| **সবজি তথ্য** | A month-by-month sowing guide, plus a full growing guide for each of 36 vegetables. |

## How the "multi-agent" part works

Each agent is a Python function in `krishi/agents.py`:

- **Master Coordinator** (`coordinate_chat`, `coordinate_diagnose`, `coordinate_plan`) reads the question, picks agents, and merges their output into the standard Bengali format.
- Vegetable Expert, Season & Weather, Disease Diagnosis, Pest Management, Soil & Fertilizer, Irrigation & Farm Management, Problem Solver, Business & Cost, Research & Verification, Symptom Scanner, and Smart Farming Planner.

The facts live in `krishi/knowledge.py`: 36 vegetables, 34 diseases and disorders, 17 pests, 11 problem types, regional risks by district, and the seasons.

**Safety rules built in:** no pesticide product names or doses, IPM and biological control first, alternatives always shown, all money figures come from the farmer, and every answer points to the Upazila Agriculture Office or Krishi Call Centre 16123.

## Limits (because there's no AI)

- It **can't read photos**. The scanner uses ticked symptoms instead.
- The chat **matches keywords**. It works best when the farmer names the crop and the symptom or month. Unusual phrasing may get the help message.
- It only knows what is in `knowledge.py`. To add crops or fix a fact, edit that file.

## Deploy on Render (free)

1. Push this folder to GitHub:
   ```bash
   git init && git add . && git commit -m "Krishi AI"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/krishi-ai.git
   git push -u origin main
   ```
2. On dashboard.render.com, click **New > Blueprint** and pick the repo. Render reads `render.yaml`.
   Or set it up manually with **New > Web Service**:
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. Wait for "Live", then open your `onrender.com` link. You don't need to set any environment variables.

On the free plan, the app sleeps when nobody uses it. The first visit after a break takes about a minute.

## Run on your computer

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python test_krishi.py             # quick self-test
uvicorn app:app --reload          # open http://localhost:8000
```

## Files

```
app.py               FastAPI server and API routes
krishi/knowledge.py  the knowledge base (edit facts here)
krishi/agents.py     the agents and the Master Coordinator
static/index.html    the Bengali web app
test_krishi.py       self-test
render.yaml          Render settings
```

The content is general guidance compiled for Bangladesh conditions. Sowing months, spacing, and durations vary by variety and region. Have a local agriculture officer review `knowledge.py` before you use it widely.
