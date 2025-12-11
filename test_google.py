# test_google.py
import os, sys, traceback
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

def main():
    load_dotenv()  # подтянет .env рядом с файлом

    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    folder_id = os.getenv("DRIVE_FOLDER_ID")
    prefix    = os.getenv("EXPORT_PREFIX", "WorkLog")

    print("[i] JSON:", json_path)
    print("[i] FOLDER_ID:", folder_id)
    print("[i] PREFIX:", prefix)

    if not json_path or not os.path.exists(json_path):
        print("[!] Не найден JSON ключ сервисного аккаунта. Проверь путь в .env (GOOGLE_SERVICE_ACCOUNT_JSON).")
        sys.exit(1)

    try:
        creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
        print("[i] Service account email:", getattr(creds, "service_account_email", "(no email field)"))

        drive = build("drive", "v3", credentials=creds)
        sheets = build("sheets", "v4", credentials=creds)

        # 1) Создаём пустую Google Sheet в папке
        name = f"{prefix}_TEST_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        file = drive.files().create(body=file_metadata, fields="id, webViewLink, name, parents").execute()
        sheet_id = file["id"]
        link = file["webViewLink"]
        print("[+] Таблица создана:", file["name"])
        print("[+] Ссылка:", link)

        # 2) Пишем заголовок и одну тестовую строку
        body = {
            "values": [
                ["Фамилия Имя", "Вид работы", "Локация", "Дата", "Часы"],
                ["Тест Пользователь", "пример", "склад", datetime.now().date().isoformat(), 5],
            ]
        }
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1:E2",
            valueInputOption="RAW",
            body=body,
        ).execute()
        print("[+] Данные записаны. Готово!")

    except HttpError as e:
        print("[!] Google API HttpError:", e)
        # Подсказываем частые причины
        if e.resp.status in (403, 404):
            print("    Часто это значит, что ПАПКА НЕ РАССШАРЕНА на сервисный аккаунт.")
            print("    Открой Drive → папка → Share (Доступ) → добавь e-mail сервисного аккаунта как Editor.")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print("[!] Ошибка:", e)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
