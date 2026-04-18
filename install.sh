#!/bin/bash
# Первичная настройка Terra App API на VPS (FastAPI + venv в backend/).
# Запуск: sudo bash install.sh  (или от root)

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Запустите с sudo: sudo bash install.sh"
  exit 1
fi

APP_DIR="${APP_DIR:-/opt/terra_app}"
echo "Каталог приложения: $APP_DIR"
cd "$APP_DIR"

if [ ! -f backend/requirements.txt ]; then
  echo "Не найден backend/requirements.txt — ожидается клон репозитория Terra App."
  exit 1
fi

apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git

RUN_AS="${SUDO_USER:-${APP_USER:-}}"
if [ -z "$RUN_AS" ] || ! id "$RUN_AS" &>/dev/null; then
  echo "Задайте пользователя: APP_USER=fred23 sudo -E bash install.sh"
  exit 1
fi
chown -R "$RUN_AS:$RUN_AS" "$APP_DIR" 2>/dev/null || true
echo "Создание venv в backend/.venv (пользователь $RUN_AS) ..."
sudo -u "$RUN_AS" bash -c "cd '$APP_DIR/backend' && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt"

echo ""
echo "Дальше:"
echo "  1) Настройте $APP_DIR/backend/.env (см. README_APP.md, app/core/config.py)."
echo "  2) Скопируйте terra-api.service.example в /etc/systemd/system/terra-api.service, исправьте User и пути."
echo "  3) sudo systemctl daemon-reload && sudo systemctl enable --now terra-api"
