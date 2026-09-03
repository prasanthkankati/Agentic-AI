
```powershell
# 1) create & activate venv (only once)
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .venv\Scripts\Activate.ps1

# 2) install requirements and Playwright browser
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# 3) copy .env example and add your key (manual edit)
Copy-Item .env.example .env
notepad .env

# 4) run pipeline with browser visible
$env:HEADLESS="false"
python run_project.py

# 5) (optional) summarize generated tests and run pytest
$env:HEADLESS="false"
python scripts/run_and_log_tests.py
```

macOS / Linux (bash):
```bash
# 1) create & activate venv (only once)
python3 -m venv .venv
source .venv/bin/activate

# 2) install requirements and Playwright browser
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# 3) copy .env example and add your key (manual edit)
cp .env.example .env
${VISUAL:-nano} .env

# 4) run pipeline with browser visible
export HEADLESS=false
python run_project.py

# 5) (optional) summarize generated tests and run pytest
export HEADLESS=false
python scripts/run_and_log_tests.py
```

