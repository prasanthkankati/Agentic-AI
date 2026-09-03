# Setup — 3 steps

## Step 1 — Paste your API key

Open the file **`.env`** in VS Code.

Find **line 8**:

```
GOOGLE_API_KEY=PASTE_YOUR_KEY_HERE
```

Replace `PASTE_YOUR_KEY_HERE` with your key from
https://aistudio.google.com/app/api-keys

It should end up looking like this — no quotes, no spaces around `=`:

```
GOOGLE_API_KEY=AQ.Ab8RN6your_actual_key_here
```

Save with Ctrl+S. **That is the only file you edit.**

## Step 2 — Install

Open the VS Code terminal (Ctrl+`) in this folder:

```
pip install -r requirements.txt
playwright install chromium
```

## Step 3 — Run

Run either of these:

```
python run_project.py
```

To watch the crawler browser while it runs:

```
$env:HEADLESS="false"
python run_project.py
```

or open `agentic_ai_capstone_colab.ipynb` in VS Code, select a Python kernel
when prompted, then **Run All**.

The notebook reads your key from `.env` automatically. Watch the preflight
cell — if it does not print `ALL CHECKS PASSED`, stop and fix what it reports.

---

## Before you submit or push to GitHub

`.gitignore` already excludes `.env`, so `git push` will not upload your key.

If you are zipping the folder by hand instead, **delete `.env` first**.
`.env.example` stays — it shows the format without exposing anything.
