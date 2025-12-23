# Terra Mini App (frontend)

## Запуск

1) Убедись, что backend запущен (по умолчанию `http://localhost:8080`).

2) Установи зависимости:

```bash
npm i
```

3) Запусти dev сервер:

```bash
npm run dev
```

## Как работает авторизация

- В `App.tsx` выполняется bootstrap:
  - `POST /api/auth/telegram` с `initData` (создаёт cookie-сессию)
  - затем `GET /api/me` для получения профиля и меню

## Прокси

Vite проксирует `/api/*` на `VITE_API_TARGET` (по умолчанию `http://localhost:8080`).
