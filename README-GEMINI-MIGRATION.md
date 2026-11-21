# Krishi AI — Gemini migration

Replace the existing root-level `app.py`, `requirements.txt`, and `render.yaml` with these files. Keep your existing `static/` folder and `static/index.html` unchanged. The backend preserves `/api/config`, `/api/agent`, and `/healthz` and accepts the existing `prompt`, optional `tier`, and optional base64 image data URLs.

## Configure Gemini

1. Create a Gemini API key in Google AI Studio: https://aistudio.google.com/apikey
2. In Render, open the `krishi-ai` service → Environment.
3. Add `GEMINI_API_KEY` and paste the key as its value. Keep it private; never put it in frontend JavaScript or commit it to GitHub.
4. Remove `ANTHROPIC_API_KEY` if you no longer use Anthropic.
5. Save changes and let Render redeploy.

Default models are `gemini-3.8-flash` and `gemini-3.5-flash-lite`. If either model is unavailable to your API project, set `MODEL_DEFAULT` or `MODEL_QUICK` to a model that your Google AI Studio project supports.

## Push the changes

```bash
git add app.py requirements.txt render.yaml
git commit -m "Migrate Krishi AI to Gemini"
git push
```

## Test

- `/healthz` should return `ok`.
- `/api/config` should return JSON.
- Test a text question and then the plant-photo feature.
- If a request fails, inspect Render → Logs for `Gemini error:`. Do not share API keys.
