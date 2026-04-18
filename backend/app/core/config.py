from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "TerraApp API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-long-random-string"

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "terra"
    DB_PASS: str = "terra"
    DB_NAME: str = "terra_app"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Admin
    FIRST_ADMIN_LOGIN: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "admin123"

    # Sentry
    SENTRY_DSN: str = ""

    # Google Sheets (optional, keep bot integration)
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "service_account.json"
    DRIVE_FOLDER_ID: str = ""
    BRIGADIER_FOLDER_ID: str = ""

    # Expo Push
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"

    # Базовый URL для пригласительных ссылок (веб / deep link). Пусто = фронт подставит origin.
    PUBLIC_JOIN_BASE_URL: str = ""


settings = Settings()
