# TerraApp — Corporate Mobile Platform

Self-hosted corporate platform with React Native mobile app (iOS + Android), React AdminPanel, and FastAPI backend. Migrated from the existing Telegram bot (`bot_polya.py`).

## Quick Start (Development)

### 1. Start infrastructure (PostgreSQL + Redis)
```bash
docker compose -f docker-compose.dev.yml up db redis -d
```

### 2. Backend
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp ../.env.backend .env
alembic upgrade head
python create_admin.py --login admin --password admin123 --name "Администратор"
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 3. Web AdminPanel
```bash
cd web
npm install
npm run dev
```
Open: http://localhost:3000 — login: `admin` / `admin123`

**AdminPanel (навигация):** главная (иконка дома) с названием компании и кнопками «Статистика» и «Создать ссылку»; пункты «Пользователи» и «Группы» убраны; «Отчёты» и «Экспорт» объединены в «Отчёты и экспорт». API: `GET/POST /api/v1/admin/...` (миграция `002` для `tenant_settings` и `invite_links`). При необходимости задайте `PUBLIC_JOIN_BASE_URL` в `.env` бэкенда.

### 4. Mobile App
```bash
cd mobile
npm install
npx expo start
```
Scan QR with Expo Go (iOS/Android) or press `a`/`i` for simulator.

Set `EXPO_PUBLIC_API_URL=http://YOUR_LOCAL_IP:8000/api/v1` in `mobile/.env`.

**Синхрон с админкой:** списки форм (ОТД, бригадир и др.) и справочники подтягиваются с API при возврате приложения из фона, при открытии вкладки «Главная», при свайпе-обновлении на главной и при восстановлении сети (`refetchOnReconnect`). Данные хранятся в TanStack Query (`mobile/src/lib/syncDataCaches.ts`, хук `useSyncFormsAndDictionaries`).

---

## Migrate from existing SQLite bot data
```bash
cd backend
python migrate_from_sqlite.py --sqlite-path ../reports.db --default-password Change123!
```
All existing users get a login = their Telegram username (or phone/ID) and the default password.

---

## Project Structure

```
terra_app/
├── backend/              # FastAPI + PostgreSQL + Redis
│   ├── app/
│   │   ├── api/          # Auth, Users, Reports, Forms, Chat, Groups, Export
│   │   ├── models/       # SQLAlchemy async models
│   │   ├── schemas/      # Pydantic v2 schemas
│   │   ├── services/     # Excel export, Push notifications
│   │   ├── workers/      # ARQ background tasks (daily export)
│   │   └── core/         # Config, DB, Security, Redis
│   ├── alembic/          # DB migrations
│   ├── create_admin.py   # First admin setup utility
│   └── migrate_from_sqlite.py  # One-time SQLite → Postgres migration
├── mobile/               # React Native (Expo SDK 52)
│   └── src/
│       ├── screens/      # Login, Home, OTD form, Brig form, Reports,
│       │                 # Stats, Chat, Profile, DynamicForm
│       ├── navigation/   # Stack + Bottom tabs
│       ├── api/          # Axios clients (auth, reports, chat, forms)
│       └── store/        # Zustand (auth state)
├── web/                  # React AdminPanel (Vite + Tailwind)
│   └── src/
│       ├── pages/        # Dashboard, Users, Groups, Forms Builder,
│       │                 # Reports, Export, ChatRooms
│       ├── components/   # Sidebar Layout
│       └── api/          # Axios client with JWT auto-refresh
├── docker-compose.dev.yml
└── .github/workflows/ci.yml
```

---

## API Reference (v1)

Base: `http://localhost:8000/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register new account |
| POST | `/auth/login` | Login → JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Invalidate refresh token |
| GET | `/users/me` | Current user profile |
| PATCH | `/users/me` | Update profile |
| GET | `/users` | List users (admin) |
| PATCH | `/users/{id}` | Update user role/status (admin) |
| GET | `/dictionaries` | All dictionaries |
| POST | `/reports` | Create OTD report |
| GET | `/reports` | List my reports |
| DELETE | `/reports/{id}` | Delete report |
| POST | `/brig/reports` | Create brigadier report |
| GET | `/stats?period=week` | Statistics (today/week/month) |
| GET | `/forms` | List forms for current role |
| POST | `/forms` | Create form template (admin) |
| POST | `/form-responses` | Submit dynamic form |
| GET | `/chat/rooms` | List my chat rooms |
| POST | `/chat/rooms` | Create chat room |
| GET | `/chat/rooms/{id}/messages` | Fetch messages |
| WS | `/chat/ws/{room_id}?token=` | WebSocket chat |
| GET | `/groups` | Group tree |
| POST | `/groups` | Create group (admin) |
| POST | `/groups/{id}/members` | Add member |
| POST | `/export/excel/otd` | Download OTD Excel |
| POST | `/export/excel/accounting` | Download ЗП-ОТД Excel |
| GET | `/export/stats/admin` | Admin stats by user |

---

## Roles

| Role | Access |
|------|--------|
| `admin` | Full access, AdminPanel |
| `accountant` | Accounting export |
| `brigadier` | Brigadier reports |
| `tim` | TIM reports |
| `it` | IT menu |
| `user` | Basic reports |

---

## Production Deployment

### Backend
```bash
docker compose -f docker-compose.dev.yml up -d
```

### AdminPanel (static)
```bash
cd web && npm run build
# Serve dist/ with nginx
```

### Mobile (EAS Build)
```bash
cd mobile
npm install -g eas-cli
eas build --platform all
```

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, asyncpg, Redis, ARQ, openpyxl
- **Mobile**: React Native, Expo SDK 52, React Navigation 6, TanStack Query 5, Zustand
- **Web**: React 18, Vite, TypeScript, Tailwind CSS, TanStack Query 5
- **Auth**: JWT (access 15 min + refresh 30 days in Redis), bcrypt
- **Realtime**: FastAPI WebSocket + in-process broadcast (scale with Redis pub/sub)
- **Push**: Expo Push Notification API (FCM + APNs abstraction)
- **Export**: openpyxl — ported from existing bot_polya.py
