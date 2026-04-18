# 🚀 Быстрый старт: Экспорт в Google Sheets

## Шаг 1: Установка зависимостей

```bash
pip install apscheduler
```

Или установите все зависимости сразу:
```bash
pip install -r requirements.txt
```

## Шаг 2: Настройка .env файла

Добавьте в ваш `.env` файл следующие строки:

```env
# Google Sheets настройки
OAUTH_CLIENT_JSON=oauth_client.json
TOKEN_JSON_PATH=token.json
DRIVE_FOLDER_ID=ваш_id_папки_на_google_drive
EXPORT_PREFIX=WorkLog
AUTO_EXPORT_ENABLED=true
AUTO_EXPORT_CRON=0 9 * * 1
```

### Как получить DRIVE_FOLDER_ID:

1. Откройте Google Drive в браузере
2. Создайте новую папку (или откройте существующую)
3. Откройте эту папку
4. Скопируйте ID из URL:
   ```
   https://drive.google.com/drive/folders/[ВОТ_ЭТО_ID_ПАПКИ]
   ```
5. Вставьте этот ID в `.env` файл

## Шаг 3: Проверка файлов

Убедитесь, что у вас есть файл `oauth_client.json` с учетными данными OAuth клиента Google.

Если его нет, вам нужно:
1. Зайти в [Google Cloud Console](https://console.cloud.google.com/)
2. Создать проект (или выбрать существующий)
3. Включить Google Drive API и Google Sheets API
4. Создать OAuth 2.0 Client ID
5. Скачать JSON файл и сохранить как `oauth_client.json`

## Шаг 4: Первый запуск

См. **[README_APP.md](README_APP.md)** — экспорт и API идут через backend Terra App.

```bash
cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

При первом запуске откроется браузер для авторизации Google:
1. Выберите ваш Google аккаунт
2. Разрешите доступ к Google Drive и Google Sheets
3. Токен доступа сохранится в `token.json`

## Шаг 5: Первый экспорт

### Вариант А: Ручной экспорт

1. Откройте бота в Telegram
2. Нажмите "🧰 Меню"
3. Нажмите "⚙️ Админ"
4. Нажмите "📤 Экспорт в Google Sheets"
5. Дождитесь сообщения об успешном экспорте

### Вариант Б: Автоматический экспорт

Если `AUTO_EXPORT_ENABLED=true`, бот будет автоматически экспортировать отчеты согласно расписанию.

По умолчанию: каждый понедельник в 9:00

## 🎉 Готово!

Теперь ваш бот будет автоматически экспортировать отчеты в Google Sheets!

Все отчеты будут сохраняться в формате:
- **Дата** | **Фамилия Имя** | **Место работы** | **Вид работы** | **Количество часов**

Каждый месяц создается отдельная таблица с названием `WorkLog_YYYY_MM`.

## 📝 Настройка расписания

Формат `AUTO_EXPORT_CRON`: `минута час день месяц день_недели`

Примеры:
```env
# Каждый понедельник в 9:00
AUTO_EXPORT_CRON=0 9 * * 1

# Каждый день в полночь
AUTO_EXPORT_CRON=0 0 * * *

# Каждую пятницу в 18:00
AUTO_EXPORT_CRON=0 18 * * 5

# Первого числа каждого месяца в 9:00
AUTO_EXPORT_CRON=0 9 1 * *
```

## ❓ Проблемы?

См. подробную документацию: `GOOGLE_SHEETS_SETUP.md`

## 🔍 Проверка экспорта

1. Откройте Google Drive
2. Перейдите в указанную папку (DRIVE_FOLDER_ID)
3. Вы увидите таблицы с названиями `WorkLog_2025_10`, `WorkLog_2025_11` и т.д.
4. Откройте таблицу - там будут все экспортированные отчеты

