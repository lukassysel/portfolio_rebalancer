#!/usr/bin/env bash
# Spuštění aplikace na tomto počítači (macOS / Linux). Potřebuje jen internet při prvním spuštění.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "Instaluji uv (správce Pythonu, jednorázově)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "Připravuji Python a knihovny (poprvé to může trvat minutu)…"
uv sync --frozen --quiet
PORT="${PORT:-8000}"
URL="http://localhost:$PORT"
echo ""
echo "Aplikace běží na $URL  – ukončíte ji klávesami Ctrl+C."
( sleep 3; command -v open >/dev/null 2>&1 && open "$URL" || command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" || true ) >/dev/null 2>&1 &
exec uv run uvicorn rebalancer.api.app:app --host 127.0.0.1 --port "$PORT"
