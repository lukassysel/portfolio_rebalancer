@echo off
rem Spusteni aplikace na tomto pocitaci (Windows).
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul || powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo Pripravuji Python a knihovny (poprve to muze trvat minutu)...
uv sync --frozen --quiet
echo Aplikace bezi na http://localhost:8000 - ukoncite ji klavesami Ctrl+C.
start "" http://localhost:8000
uv run uvicorn rebalancer.api.app:app --host 127.0.0.1 --port 8000
