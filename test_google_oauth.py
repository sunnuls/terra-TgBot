import os, pathlib, datetime as dt
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Разрешения (хватает этих двух)
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

BASE = pathlib.Path(__file__).resolve().parent
load_dotenv(BASE / ".env")

CLIENT_JSON = os.getenv("OAUTH_CLIENT_JSON", "")
FOLDER_ID    = os.getenv("DRIVE_FOLDER_ID", "")
PREFIX       = os.getenv("EXPORT_PREFIX", "WorkLog")
TOKEN_JSON   = BASE / "token.json"

def get_creds():
    creds = None
    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_JSON, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_JSON, SCOPES)
            creds = flow.run_local_server(port=0)  # откроет браузер
        TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")
    return creds

def main():
    if not CLIENT_JSON or not pathlib.Path(CLIENT_JSON).exists():
        print("[ERR] Не найден OAUTH_CLIENT_JSON в .env или файл отсутствует.")
        return
    if not FOLDER_ID:
        print("[ERR] DRIVE_FOLDER_ID пуст. Укажи ID папки в .env")
        return

    creds = get_creds()
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)

    today = dt.date.today().strftime("%Y-%m-%d")
    file_name = f"{PREFIX}_{today}"

    # 1) Создаём пустую Google Sheets в нужной папке
    file_metadata = {
        "name": file_name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [FOLDER_ID],
    }
    file = drive.files().create(body=file_metadata, fields="id, webViewLink, name").execute()
    ssid = file["id"]
    link = file["webViewLink"]
    print("[OK] Создан файл:", file["name"], link)

    # 2) Пишем пару ячеек
    body = {
        "valueInputOption": "USER_ENTERED",
        "data": [{
            "range": "A1:E1",
            "values": [["ФИО", "Вид работ", "Место", "Дата", "Часы"]],
        }, {
            "range": "A2:E2",
            "values": [["Тест ФИО", "Проверка", "Склад", today, 5]],
        }],
    }
    sheets.spreadsheets().values().batchUpdate(spreadsheetId=ssid, body=body).execute()
    print("[OK] Данные записаны. Ссылка:", link)

if __name__ == "__main__":
    main()

