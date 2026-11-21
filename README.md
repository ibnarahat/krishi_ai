# Krishi AI (কৃষি AI) - Python version

A multi-agent farming advisor for Bangladesh. It has 11 specialist agents and a Master Coordinator, all in Bengali, across three tools: advice chat, a plant disease photo scanner and a smart farming planner.

## Files

- `app.py` is the FastAPI server. It serves the app and sends each agent call to Claude, streaming the answer back. Your API key stays on the server.
- `static/index.html` is the full web app: chat, scanner, planner and a live agent board.
- `requirements.txt` lists the Python packages.
- `render.yaml` holds the Render settings.

## Deploy on Render

1. **Get an API key.** On console.anthropic.com, add billing credit, then create a key under API Keys.
2. **Push to GitHub.** Create an empty repo called `krishi-ai`, then in this folder run:
   ```bash
   git init
   git add .
   git commit -m "Krishi AI Python"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/krishi-ai.git
   git push -u origin main
   ```
3. **Create the service.** On dashboard.render.com, click **New > Blueprint** and pick the repo. Render reads `render.yaml` and sets up everything.
   Manual setup also works: click **New > Web Service** and use:
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. **Add the key.** Paste your key into `ANTHROPIC_API_KEY`. You can change it later under the service's **Environment** tab.
5. **Open the app.** Once Render shows "Live", open your `https://krishi-ai-xxxx.onrender.com` link.

Each `git push` to `main` redeploys the app automatically.

## Settings (Render > Environment)

| Variable | What it does | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key (required) | none |
| `MODEL_DEFAULT` | Model the specialists and coordinator use | `claude-sonnet-5-5` |
| `MODEL_QUICK` | Model the router uses to pick agents | `claude-haiku-5-5` |
| `ACCESS_CODE` | Makes visitors enter this code first | off |
| `RATE_LIMIT_PER_MIN` | Most API calls one visitor can make per minute | `40` |
| `MAX_TOKENS` | Longest reply one agent can give | `4000` |

Set `ACCESS_CODE` before you share the link. Otherwise anyone who finds it can spend your API credit.

## Run on your computer

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: set ANTHROPIC_API_KEY=sk-ant-...
uvicorn app:app --reload
# open http://localhost:8000
```

## Notes

- Each farmer question makes about 4 to 9 Claude calls: a router, the specialists running in parallel and a coordinator.
- On Render's free plan the app sleeps when nobody uses it, so the first visit after a break can take about a minute.
- The agents work from Claude's own knowledge of BARI and DAE guidance and don't browse the web. Prices come from the farmer or are labelled as assumptions.
- To change what an agent does, edit the `A` list and the `COORD_*` prompts in `static/index.html`.
