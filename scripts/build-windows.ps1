$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
$python = Get-Command py -ErrorAction SilentlyContinue
if (!$python) { throw "Python 3.11+ is required to build WorkPulse. Install Python from python.org with the Python Launcher, then rerun this script." }
if (!(Test-Path ".venv\Scripts\python.exe")) {
  & py -3.11 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Python 3.11 was not found. Install Python 3.11+ with the Python Launcher, then rerun this script." }
}
$venvPython = ".\.venv\Scripts\python.exe"
& $venvPython -m pip install -r backend\requirements.txt pillow
if ($LASTEXITCODE -ne 0) { throw "Python build dependencies could not be installed." }
$env:PYTHONPATH = (Resolve-Path "backend").Path
& $venvPython -m pytest -q backend\tests
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }
& $venvPython scripts\make_icons.py
& $venvPython -m PyInstaller --noconfirm --clean --onefile --name workpulse-backend --paths backend --distpath backend\dist --workpath backend\build --add-data "backend\alembic.ini;." --add-data "backend\alembic;alembic" --collect-submodules uvicorn --collect-submodules sqlalchemy.dialects.sqlite --hidden-import win32timezone backend\run_backend.py
if ($LASTEXITCODE -ne 0) { throw "Agent build failed" }
Push-Location desktop
try {
  npm install
  if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
  npm run build:win
  if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
} finally { Pop-Location }
Write-Host "Installer created: desktop\release\WorkPulse-Setup.exe"
