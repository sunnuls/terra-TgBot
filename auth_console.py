# auth_console.py
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json, os

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

CLIENT_PATH = r"C:\bot\oauth_client.json"      # путь к загруженному OAuth JSON
TOKEN_PATH  = r"C:\bot\oauth_token.json"       # сюда сохранится токен

def main():
    if not os.path.exists(CLIENT_PATH):
        print(f"[!] Не найден файл клиента: {CLIENT_PATH}")
        return

    print("[i] Запускаю консольный OAuth-поток (без автозапуска браузера)…")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_PATH, SCOPES)

    # Консольный поток: выдаст URL в терминал, скопируй в браузер,
    # войди в аккаунт и вставь код обратно в консоль.
    creds = flow.run_console()

    # Сохранить токен на диск
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("[✓] Готово! Токен сохранён:", TOKEN_PATH)

if __name__ == "__main__":
    main()
