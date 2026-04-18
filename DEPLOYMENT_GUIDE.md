# Деплой

Инструкции для старого Telegram-бота из этого репозитория удалены вместе с кодом бота.

**Актуальный продакшен** — приложение Terra App (FastAPI + web + mobile). См. **[README_APP.md](README_APP.md)**.

Кратко по API на Linux:

1. Клон репозитория, `cd backend`, `python3 -m venv .venv`, `.venv/bin/pip install -r requirements.txt`
2. Настроить `backend/.env` (см. `backend/app/core/config.py`)
3. Пример systemd: **`terra-api.service.example`** → `/etc/systemd/system/terra-api.service`, затем `systemctl enable --now terra-api`

Docker для локальной разработки: **`docker-compose.dev.yml`**.
