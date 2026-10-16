$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
if (!(Test-Path ".venv\Scripts\python.exe")) { py -3.11 -m venv .venv }
& .venv\Scripts\python.exe -m pip install -r backend\requirements.txt pillow
$env:PYTHONPATH = (Resolve-Path "backend").Path
& .venv\Scripts\python.exe -m pytest -q backend\tests
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }
& .venv\Scripts\python.exe scripts\make_icons.py
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --name workpulse-backend --paths backend --distpath backend\dist --workpath backend\build --add-data "backend\alembic.ini;." --add-data "backend\alembic;alembic" --collect-submodules uvicorn --collect-submodules sqlalchemy.dialects.sqlite --hidden-import win32timezone backend\run_backend.py
if ($LASTEXITCODE -ne 0) { throw "Agent build failed" }
Push-Location desktop
try {
  npm install
  if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
  npm run build:win
  if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
} finally { Pop-Location }
Write-Host "Installer created: desktop\release\WorkPulse-Setup.exe"
