from __future__ import annotations
import os, json, sys
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
BASE = Path(r"C:\bot")
CLIENT = BASE / "oauth_client.json"
TOKEN  = BASE / "oauth_token.json"

def get_creds():
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
        if creds and creds.valid:
            return creds
    # интерактивный вход
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
        try:
            creds = flow.run_local_server(port=0)
        except Exception:
            creds = flow.run_console()
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
        return creds
    except Exception as e:
        print("[!] Не удалось запустить OAuth:", e)
        print("Убедись, что файл есть:", CLIENT)
        sys.exit(1)

def main():
    load_dotenv(BASE / ".env")
    folder_id = os.getenv("DRIVE_FOLDER_ID") or ""
    if not folder_id:
        print("[!] В .env нет DRIVE_FOLDER_ID"); sys.exit(1)

    print("[i] OAuth client:", CLIENT)
    print("[i] token:", TOKEN)
    print("[i] DRIVE_FOLDER_ID:", folder_id)

    creds = get_creds()
    drive = build("drive", "v3", credentials=creds)

    meta = {
        "name": "WorkLog_OAuth_Test",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
    }
    try:
        file = drive.files().create(body=meta, fields="id, webViewLink, name, parents").execute()
        print("[✓] Создан файл:", file["name"])
        print("[✓] Ссылка:", file["webViewLink"])
    except HttpError as e:
        print("[!] Google API HttpError:", e)
        print("Подсказки:")
        print("  • 403 storageQuotaExceeded — у АККАУНТА, под которым вошёл OAuth, нет места на Диске.")
        print("  • 404 notFound по folder_id — неверный ID папки или нет доступа.")
        print("  • Проверь, что папка расшарена для твоего аккаунта (если это чужая папка).")

if __name__ == "__main__":
    main()
