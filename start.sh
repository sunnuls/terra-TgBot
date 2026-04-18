#!/bin/bash
# Запуск API Terra App (FastAPI) на Linux-сервере

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"

echo "=== Terra App API ==="

if [ ! -d "$BACKEND/.venv" ]; then
  echo "Создаём venv: $BACKEND/.venv"
  python3 -m venv "$BACKEND/.venv"
fi

# shellcheck source=/dev/null
source "$BACKEND/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$BACKEND/requirements.txt"

if [ ! -f "$BACKEND/.env" ]; then
  echo "Нет файла $BACKEND/.env — скопируйте настройки из README_APP / backend (SECRET_KEY, БД и т.д.)."
  exit 1
fi

cd "$BACKEND"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
