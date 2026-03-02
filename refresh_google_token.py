#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обновления токена Google OAuth
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Загружаем переменные окружения
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

OAUTH_CLIENT_JSON = os.getenv("OAUTH_CLIENT_JSON", "oauth_client.json")
TOKEN_JSON_PATH = Path(os.getenv("TOKEN_JSON_PATH", "token.json"))

def refresh_token():
    """Обновить токен Google OAuth"""
    
    print("=" * 60)
    print("Обновление токена Google OAuth")
    print("=" * 60)
    
    # Проверяем наличие OAuth клиента
    if not Path(OAUTH_CLIENT_JSON).exists():
        print(f"\n❌ Ошибка: Файл '{OAUTH_CLIENT_JSON}' не найден!")
        print("   Убедитесь, что у вас есть файл с учетными данными OAuth клиента.")
        return False
    
    print(f"\n✓ Найден OAuth клиент: {OAUTH_CLIENT_JSON}")
    
    # Удаляем старый токен если есть
    if TOKEN_JSON_PATH.exists():
        print(f"✓ Удаляем старый токен: {TOKEN_JSON_PATH}")
        TOKEN_JSON_PATH.unlink()
    
    print("\n🔐 Начинаем авторизацию...")
    print("   Сейчас будет выдана ссылка для входа в Google аккаунт.")
    print("   Разрешите доступ к Google Drive и Google Sheets.")
    print()
    
    try:
        # Создаем flow для авторизации
        flow = InstalledAppFlow.from_client_secrets_file(
            OAUTH_CLIENT_JSON, 
            SCOPES
        )
        
        # На headless-серверах (без DISPLAY) браузер открыть нельзя.
        # В таком режиме запускаем локальный callback-сервер без попытки открыть браузер.
        is_headless = (os.name != "nt") and (not os.getenv("DISPLAY"))
        try:
            if is_headless:
                creds = flow.run_local_server(
                    port=int(os.getenv("OAUTH_LOCAL_PORT", "8080")),
                    open_browser=False,
                    access_type="offline",
                    prompt="consent",
                )
            else:
                creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        except Exception:
            creds = flow.run_console(access_type="offline", prompt="consent")
        
        # Сохраняем токен
        TOKEN_JSON_PATH.write_text(creds.to_json(), encoding="utf-8")
        
        print("\n" + "=" * 60)
        print("✅ УСПЕХ! Токен успешно обновлен!")
        print("=" * 60)
        print(f"\n✓ Токен сохранен в: {TOKEN_JSON_PATH}")
        print("\nТеперь вы можете запустить бота:")
        print("   python bot_polya.py")
        print()
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ОШИБКА при авторизации!")
        print("=" * 60)
        print(f"\n{e}\n")
        print("Возможные причины:")
        print("  1. Неверный файл oauth_client.json")
        print("  2. OAuth клиент не настроен в Google Cloud Console")
        print("  3. Браузер не смог открыться автоматически")
        print()
        return False

if __name__ == "__main__":
    success = refresh_token()
    if not success:
        exit(1)

