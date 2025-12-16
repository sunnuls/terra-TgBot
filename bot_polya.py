# bot_polya.py
# -*- coding: utf-8 -*-

import asyncio
import html
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import calendar
import time
import random

import logging
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    ChatPermissions,
    ChatMemberAdministrator,
    ChatMemberOwner,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from dotenv import load_dotenv

# Google Sheets API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scheduler для автоматического экспорта
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# -----------------------------
# Конфиг
# -----------------------------

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
assert TOKEN, "❌ Ошибка: TELEGRAM_TOKEN или BOT_TOKEN не найден в .env"

STARTED_AT = datetime.now()

def _read_git_short_sha(repo_dir: Path) -> Optional[str]:
    """
    Best-effort git SHA reader without requiring `git` binary.
    Works when `.git` is present in the runtime filesystem (e.g., on server checkout).
    """
    try:
        head_path = repo_dir / ".git" / "HEAD"
        if not head_path.exists():
            return None
        head = head_path.read_text(encoding="utf-8", errors="ignore").strip()
        sha: Optional[str] = None

        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            ref_path = repo_dir / ".git" / Path(ref)
            if ref_path.exists():
                sha = ref_path.read_text(encoding="utf-8", errors="ignore").strip()
            else:
                packed = repo_dir / ".git" / "packed-refs"
                if packed.exists():
                    for line in packed.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("^"):
                            continue
                        parts = line.split(" ", 1)
                        if len(parts) == 2 and parts[1].strip() == ref:
                            sha = parts[0].strip()
                            break
        else:
            sha = head

        if sha and len(sha) >= 7:
            return sha[:7]
        return sha
    except Exception:
        return None

def _safe_file_mtime_str(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"

# These are captured ON PROCESS START (import time) to prove what code is actually running.
_BOOT_REPO_DIR = Path(__file__).resolve().parent
BOOT_SHA = _read_git_short_sha(_BOOT_REPO_DIR) or os.getenv("GIT_SHA", "").strip() or "unknown"
BOOT_FILE_MTIME = _safe_file_mtime_str(Path(__file__))

def _runtime_version_info(user_id: int, username: Optional[str]) -> str:
    repo_dir = Path(__file__).resolve().parent
    # Prefer the actual working tree SHA when `.git` is available; env var can be stale.
    sha = _read_git_short_sha(repo_dir) or os.getenv("GIT_SHA", "").strip() or "unknown"
    mtime = _safe_file_mtime_str(Path(__file__))
    role = get_role_label(user_id)
    uname = (username or "").lstrip("@")
    return (
        f"version(disk): <code>{sha}</code>\n"
        f"version(boot): <code>{BOOT_SHA}</code>\n"
        f"started: <code>{STARTED_AT.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"file_mtime(disk): <code>{mtime}</code>\n"
        f"file_mtime(boot): <code>{BOOT_FILE_MTIME}</code>\n"
        f"role: <code>{role}</code>\n"
        f"user: <code>{user_id}</code> @{uname if uname else '-'}"
    )


TZ = os.getenv("TZ", "Europe/Moscow").strip()

def _parse_admin_ids(s: str) -> List[int]:
    out = []
    for part in (s or "").replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out

ADMIN_IDS = set(_parse_admin_ids(os.getenv("ADMIN_IDS", "")))
ADMIN_USERNAMES = set(
    u.strip().lower().lstrip("@")
    for u in os.getenv("ADMIN_USERNAMES", "").split(",")
    if u.strip()
)
# Роли, выдаваемые админом (IT/TIM/brigadier) + статичные списки из .env
IT_IDS = set(_parse_admin_ids(os.getenv("IT_IDS", "")))
TIM_IDS = set(_parse_admin_ids(os.getenv("TIM_IDS", "")))
IT_USERNAMES = set(
    u.strip().lower().lstrip("@")
    for u in os.getenv("IT_USERNAMES", "").split(",")
    if u.strip()
)
TIM_USERNAMES = set(
    u.strip().lower().lstrip("@")
    for u in os.getenv("TIM_USERNAMES", "").split(",")
    if u.strip()
)
BRIG_USERNAMES = set(
    u.strip().lower().lstrip("@")
    for u in os.getenv("BRIG_USERNAMES", "").split(",")
    if u.strip()
)

# Пользователи, чьи отчёты НЕ публикуем в общий чат/топик статистики,
# но продолжаем сохранять в БД и выгружать в Google Sheets.
HIDE_IDS = set(_parse_admin_ids(os.getenv("HIDE_IDS", "")))

DB_PATH = os.path.join(os.getcwd(), "reports.db")

# --- helpers: env parsing ---
def _extract_drive_folder_id(value: str) -> str:
    """
    Позволяем задавать DRIVE_FOLDER_ID как "чистый ID" или как URL папки.
    Примеры:
      - 1AbC...XyZ
      - https://drive.google.com/drive/folders/1AbC...XyZ
    """
    v = (value or "").strip()
    if not v:
        return ""
    if "drive.google.com" not in v:
        return v
    # находим /folders/<id>
    marker = "/folders/"
    if marker in v:
        tail = v.split(marker, 1)[1]
        folder_id = tail.split("?", 1)[0].split("/", 1)[0].strip()
        return folder_id
    return v

# Google Sheets настройки
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]
OAUTH_CLIENT_JSON = os.getenv("OAUTH_CLIENT_JSON", "oauth_client.json")
TOKEN_JSON_PATH = Path(os.getenv("TOKEN_JSON_PATH", "token.json"))
DRIVE_FOLDER_ID = _extract_drive_folder_id(os.getenv("DRIVE_FOLDER_ID", ""))
EXPORT_PREFIX = os.getenv("EXPORT_PREFIX", "ОТД")

# Папка для выгрузки бригадиров (отдельно от общей)
BRIGADIER_FOLDER_ID = _extract_drive_folder_id(os.getenv("BRIGADIER_FOLDER_ID", ""))
BRIG_EXPORT_PREFIX = os.getenv("BRIG_EXPORT_PREFIX", "Бригадиры")

# Расписание автоматического экспорта (каждую неделю в понедельник в 9:00)
AUTO_EXPORT_ENABLED = os.getenv("AUTO_EXPORT_ENABLED", "false").lower() == "true"
AUTO_EXPORT_CRON = os.getenv("AUTO_EXPORT_CRON", "0 9 * * 1")  # каждый понедельник в 9:00

# Моментальный экспорт при изменениях (создание/правка/удаление отчёта).
# По умолчанию включается вместе с AUTO_EXPORT_ENABLED, но можно управлять отдельно.
EXPORT_ON_CHANGE_ENABLED = os.getenv(
    "EXPORT_ON_CHANGE_ENABLED",
    ("true" if AUTO_EXPORT_ENABLED else "false"),
).lower() == "true"
EXPORT_ON_CHANGE_DEBOUNCE_SEC = int(os.getenv("EXPORT_ON_CHANGE_DEBOUNCE_SEC", "5"))

# Настройки чатов/топиков (форумов) из .env
# - WORK_CHAT_ID: id супергруппы, где идёт «работа»
# - WORK_TOPIC_ID: id топика с иконкой робота, где показываем меню/диалоги
# - STATS_CHAT_ID: id супергруппы для публикации статистики (может совпадать с WORK_CHAT_ID)
# - STATS_TOPIC_ID: id отдельного топика, куда публикуются сводки
# - READONLY_CHAT_ID: id супергруппы, где бот НЕ реагирует на команды/текст,
#   а сообщения обычных пользователей удаляются (только отчёты от бота).
def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    v = (os.getenv(name, "") or "").strip()
    if not v or v == "-":
        return default
    try:
        return int(v)
    except ValueError:
        return default

WORK_CHAT_ID = _env_int("WORK_CHAT_ID")
WORK_TOPIC_ID = _env_int("WORK_TOPIC_ID")
# if not set, stats go to the same place as the menu
STATS_CHAT_ID = _env_int("STATS_CHAT_ID", WORK_CHAT_ID)
STATS_TOPIC_ID = _env_int("STATS_TOPIC_ID", WORK_TOPIC_ID)

ROBOT_CHAT_ID = _env_int("ROBOT_CHAT_ID", WORK_CHAT_ID)
ROBOT_TOPIC_ID = _env_int("ROBOT_TOPIC_ID")
ROBOT_BANNER_TEXT = os.getenv(
    "ROBOT_BANNER_TEXT",
    "Bot instructions are available via the button below."
).strip()
ROBOT_BANNER_URL = os.getenv("ROBOT_BANNER_URL", "").strip()
ROBOT_BANNER_BUTTON = os.getenv("ROBOT_BANNER_BUTTON", "Open bot").strip()
ROBOT_BANNER_MESSAGE_ID = _env_int("ROBOT_BANNER_MESSAGE_ID")
ROBOT_NOTIFY_TEXT = os.getenv(
    "ROBOT_NOTIFY_TEXT",
    "Messages in the Robot section are managed by the bot. Use the button in the pinned post."
).strip()
STATS_NOTIFY_TEXT = os.getenv(
    "STATS_NOTIFY_TEXT",
    "The Statistics section is read-only. Reports are published automatically."
).strip()

# Модерация тем
GROUP_CHAT_ID = _env_int("GROUP_CHAT_ID")
HOURS_THREAD_ID = _env_int("HOURS_THREAD_ID")
REPORTS_THREAD_ID = _env_int("REPORTS_THREAD_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()

# "Только отчёты": в этом чате бот не отвечает на команды/текст,
# а сообщения обычных пользователей удаляются.
READONLY_CHAT_ID = _env_int("READONLY_CHAT_ID")

# -----------------------------
# Константы (дефолтные справочники)
# -----------------------------

FIELD_LOCATIONS = [
    "Фазенда",
    "Чеки Куропятника",
    "58га",
    "Фермерское",
    "Северное",
    "Чеки",
    "МТФ №3",
    "Рогачи(Б)",
    "Рогачи(М)",
    "Аренда Третьяк",
]

DEFAULT_FIELDS = FIELD_LOCATIONS

CROPS_LIST = [
    "Нет культуры",
    "Кабачок",
    "Картошка",
    "Подсолнечник",
    "Кукуруза",
    "Пшеница",
    "Горох",
    "Прочее",
]

KAMAZ_CARGO_LIST = [
    "Нет культуры",
    "Кабачок",
    "Картошка",
    "Подсолнечник",
    "Кукуруза",
    "Пшеница",
    "Горох",
    "Навоз",
    "Прочее",
]

BRIG_HAND_ACTIVITIES = [
    "ПХР",
    "Ремонт",
    "Лесополосы",
    "Прополка",
    "Уборка",
]

DEFAULT_TECH = [
    "пахота","чизелевание","дискование","культивация сплошная",
    "культивация междурядная","опрыскивание","комбайн уборка","сев","барнование",
]

DEFAULT_HAND = [
    "прополка","сбор","полив","монтаж","ремонт",
]

GROUP_TECH = "техника"
GROUP_HAND = "ручная"
GROUP_FIELDS = "поля"
GROUP_WARE = "склад"

# Специфические справочники для ОТД
OTD_TRACTORS = [
    "JD7(с)", "JD7(н)", "JD8", "JD6", "Оранжевый", "Погрузчик", "Комбайн", "Прочее",
]
OTD_TRACTOR_WORKS = [
    "Сев", "Опрыскивание", "МК", "Боронование", "Уборка", "Дискование", "Пахота", "Чизелевание", "Навоз", "Прочее",
]
OTD_FIELDS = [
    *FIELD_LOCATIONS,
]
OTD_CROPS = [
    *CROPS_LIST,
]
OTD_HAND_WORKS = [
    *BRIG_HAND_ACTIVITIES,
    "Прочее",
]

# -----------------------------
# БД
# -----------------------------

def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    with connect() as con, closing(con.cursor()) as c:
        # Базовые таблицы (создадутся, если их нет)
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
          user_id    INTEGER PRIMARY KEY,
          full_name  TEXT,
          username   TEXT,
          phone      TEXT,
          tz         TEXT,
          created_at TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS activities(
          id    INTEGER PRIMARY KEY AUTOINCREMENT,
          name  TEXT UNIQUE,
          grp   TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS locations(
          id    INTEGER PRIMARY KEY AUTOINCREMENT,
          name  TEXT UNIQUE,
          grp   TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS reports(
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at    TEXT,
          user_id       INTEGER,
          reg_name      TEXT,
          username      TEXT,
          location      TEXT,
          location_grp  TEXT,
          activity      TEXT,
          activity_grp  TEXT,
          work_date     TEXT,
          hours         INTEGER,
          chat_id       INTEGER
        )
        """)

        # --- миграции существующих таблиц ---
        def table_cols(table: str):
            return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

        # users
        ucols = table_cols("users")
        if "username" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "phone" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if "tz" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN tz TEXT")
        # уникальность телефона (если задан) — один номер = один пользователь
        try:
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique "
                "ON users(phone) WHERE phone IS NOT NULL AND TRIM(phone)<>''"
            )
        except sqlite3.IntegrityError:
            # Если в старой базе уже есть дубли телефонов — не падаем.
            logging.warning("Cannot create unique phone index (duplicates exist).")

        # reports
        rcols = table_cols("reports")
        if "reg_name" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN reg_name TEXT")
        if "location_grp" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN location_grp TEXT")
        if "activity_grp" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN activity_grp TEXT")
        if "machine_type" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN machine_type TEXT")
        if "machine_name" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN machine_name TEXT")
        if "crop" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN crop TEXT")
        if "trips" not in rcols:
            c.execute("ALTER TABLE reports ADD COLUMN trips INTEGER")

        # таблица для связи отчёта и сообщения в топике статистики
        c.execute("""
        CREATE TABLE IF NOT EXISTS stat_msgs(
          report_id  INTEGER PRIMARY KEY,
          chat_id    INTEGER,
          thread_id  INTEGER,
          message_id INTEGER,
          last_action TEXT
        )
        """)

        # таблица для хранения message_id UI (2 сообщения: главное меню + контент)
        c.execute("""
        CREATE TABLE IF NOT EXISTS ui_state(
          chat_id            INTEGER,
          user_id            INTEGER,
          menu_message_id    INTEGER,
          content_message_id INTEGER,
          updated_at         TEXT,
          PRIMARY KEY (chat_id, user_id)
        )
        """)

        # таблица для отслеживания экспортов в Google Sheets
        c.execute("""
        CREATE TABLE IF NOT EXISTS google_exports(
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          report_id     INTEGER UNIQUE,
          spreadsheet_id TEXT,
          sheet_name    TEXT,
          row_number    INTEGER,
          exported_at   TEXT,
          last_updated  TEXT,
          FOREIGN KEY (report_id) REFERENCES reports(id)
        )
        """)

        # таблица для хранения информации о месячных таблицах
        c.execute("""
        CREATE TABLE IF NOT EXISTS monthly_sheets(
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          year          INTEGER,
          month         INTEGER,
          spreadsheet_id TEXT,
          sheet_url     TEXT,
          created_at    TEXT,
          UNIQUE(year, month)
        )
        """)

        # --- таблицы экспорта БРИГАДИРОВ (отдельно от обычных reports) ---
        c.execute("""
        CREATE TABLE IF NOT EXISTS brig_google_exports(
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          brig_report_id INTEGER UNIQUE,
          spreadsheet_id TEXT,
          sheet_name    TEXT,
          row_number    INTEGER,
          exported_at   TEXT,
          last_updated  TEXT,
          FOREIGN KEY (brig_report_id) REFERENCES brigadier_reports(id)
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS brig_monthly_sheets(
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          year          INTEGER,
          month         INTEGER,
          spreadsheet_id TEXT,
          sheet_url     TEXT,
          created_at    TEXT,
          UNIQUE(year, month)
        )
        """)

        # роли, которые может назначить админ (it/tim/brigadier)
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_roles(
          user_id    INTEGER PRIMARY KEY,
          role       TEXT,
          added_by   INTEGER,
          added_at   TEXT
        )
        """)

        # бригадиры и их отчёты
        c.execute("""
        CREATE TABLE IF NOT EXISTS brigadiers(
          user_id    INTEGER PRIMARY KEY,
          username   TEXT,
          full_name  TEXT,
          added_by   INTEGER,
          added_at   TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS brigadier_reports(
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id    INTEGER,
          username   TEXT,
          work_type  TEXT,
          field      TEXT,
          shift      TEXT,
          rows       INTEGER,
          bags       INTEGER,
          workers    INTEGER,
          work_date  TEXT,
          created_at TEXT
        )
        """)

        # справочники техники (типы техники + список конкретной техники)
        c.execute("""
        CREATE TABLE IF NOT EXISTS machine_kinds(
          id    INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT UNIQUE,
          mode  TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS machine_items(
          id       INTEGER PRIMARY KEY AUTOINCREMENT,
          kind_id  INTEGER,
          name     TEXT,
          UNIQUE(kind_id, name)
        )
        """)

        # миграция machine_kinds.mode (если старая схема)
        mkcols = table_cols("machine_kinds")
        if "mode" not in mkcols:
            c.execute("ALTER TABLE machine_kinds ADD COLUMN mode TEXT")
            c.execute("UPDATE machine_kinds SET mode='list' WHERE (mode IS NULL OR mode='')")

        # дефолтные типы техники
        # mode: 'list' -> выбирать/вводить конкретную технику, 'single' -> техника без выбора имени
        c.execute("INSERT OR IGNORE INTO machine_kinds(id, title, mode) VALUES (1, 'Трактор', 'list')")
        c.execute("INSERT OR IGNORE INTO machine_kinds(id, title, mode) VALUES (2, 'КамАЗ', 'single')")

        # дефолтный список тракторов (если ещё не добавлены)
        for tname in OTD_TRACTORS:
            if (tname or "").strip().lower() == "прочее":
                continue
            c.execute("INSERT OR IGNORE INTO machine_items(kind_id, name) VALUES (1, ?)", (tname,))

        # locations
        lcols = table_cols("locations")
        if "grp" not in lcols:
            c.execute("ALTER TABLE locations ADD COLUMN grp TEXT")
            # проставим значения групп по имени
            c.execute("UPDATE locations SET grp=? WHERE (grp IS NULL OR grp='') AND name='Склад'", (GROUP_WARE,))
            c.execute("UPDATE locations SET grp=? WHERE (grp IS NULL OR grp='') AND name<>'Склад'", (GROUP_FIELDS,))

        # activities
        acols = table_cols("activities")
        if "grp" not in acols:
            c.execute("ALTER TABLE activities ADD COLUMN grp TEXT")
            # техника по списку, остальное — ручная
            placeholders = ",".join("?" * len(DEFAULT_TECH))
            if placeholders:
                c.execute(
                    f"UPDATE activities SET grp=? WHERE (grp IS NULL OR grp='') AND name IN ({placeholders})",
                    (GROUP_TECH, *DEFAULT_TECH)
                )
            c.execute("UPDATE activities SET grp=? WHERE (grp IS NULL OR grp='')", (GROUP_HAND,))

        # --- дефолтные справочники (вставляем, если ещё нет) ---
        for name in DEFAULT_FIELDS:
            c.execute("INSERT OR IGNORE INTO locations(name, grp) VALUES (?, ?)", (name, GROUP_FIELDS))
        c.execute("INSERT OR IGNORE INTO locations(name, grp) VALUES (?, ?)", ("Склад", GROUP_WARE))

        for name in DEFAULT_TECH:
            c.execute("INSERT OR IGNORE INTO activities(name, grp) VALUES (?, ?)", (name, GROUP_TECH))
        for name in DEFAULT_HAND:
            c.execute("INSERT OR IGNORE INTO activities(name, grp) VALUES (?, ?)", (name, GROUP_HAND))

        con.commit()

def upsert_user(user_id: int, full_name: Optional[str], tz: str, username: Optional[str]):
    now = datetime.now().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        row = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            if full_name and full_name.strip():
                c.execute(
                    "UPDATE users SET full_name=?, username=?, tz=?, created_at=? WHERE user_id=?",
                    (full_name.strip(), username, tz, now, user_id)
                )
            else:
                c.execute(
                    "UPDATE users SET username=?, tz=?, created_at=? WHERE user_id=?",
                    (username, tz, now, user_id)
                )
        else:
            c.execute(
                "INSERT INTO users(user_id, full_name, username, tz, created_at) VALUES(?,?,?,?,?)",
                (user_id, (full_name or None), username, tz, now)
            )
        con.commit()

def get_user(user_id: int):
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute(
            "SELECT user_id, full_name, username, phone, tz, created_at FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not r:
            return None
        return {
            "user_id": r[0],
            "full_name": r[1],
            "username": r[2],
            "phone": r[3],
            "tz": r[4] or TZ,
            "created_at": r[5],
        }

def find_user_by_username(username: str) -> Optional[dict]:
    uname = (username or "").lower().lstrip("@")
    if not uname:
        return None
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute(
            "SELECT user_id, full_name, username, phone, tz, created_at FROM users WHERE LOWER(username)=?",
            (uname,),
        ).fetchone()
        if not r:
            return None
        return {
            "user_id": r[0],
            "full_name": r[1],
            "username": r[2],
            "phone": r[3],
            "tz": r[4] or TZ,
            "created_at": r[5],
        }

def normalize_phone(raw: str) -> Optional[str]:
    """
    Нормализация телефона под формат WhatsApp UserID (как на скринах): 11 цифр, начинается с 7.
    Принимаем:
      - +7XXXXXXXXXX
      - 8XXXXXXXXXX
      - 9XXXXXXXXX (10 цифр, добавляем 7)
    Возвращаем строку из цифр, например: "79898142076"
    """
    s = (raw or "").strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return digits
    return None

def format_dt_minute(value: Optional[str]) -> str:
    """
    Форматируем datetime для Google Sheets без секунд/миллисекунд:
    YYYY-MM-DD HH:MM
    На вход приходит isoformat из БД (например 2025-12-15T22:55:25.985638).
    """
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # убираем секунды/микросекунды
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        # фолбэк: если это ISO, то первых 16 символов достаточно
        # 2025-12-15T22:55 -> 2025-12-15 22:55
        if len(s) >= 16 and s[10] in ("T", " "):
            return s[:10] + " " + s[11:16]
        return s

def set_user_phone(user_id: int, phone: Optional[str]) -> bool:
    """Сохранить телефон пользователю. Возвращает True если сохранено."""
    phone = (phone or "").strip() or None
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            # например, номер уже занят другим пользователем (unique index)
            return False

def _has_phone(u: Optional[dict]) -> bool:
    return bool((u or {}).get("phone") and str((u or {}).get("phone")).strip())

def purge_release_data() -> Dict[str, int]:
    """
    Полная очистка пользовательских данных перед релизом:
    - отчёты, регистрации, роли, связки экспортов
    Не трогаем справочники (activities/locations/техника/культуры).
    """
    tables = [
        "google_exports",
        "monthly_sheets",
        "brig_google_exports",
        "brig_monthly_sheets",
        "stat_msgs",
        "ui_state",
        "brigadier_reports",
        "brigadiers",
        "user_roles",
        "reports",
        "users",
    ]
    counts: Dict[str, int] = {}
    with connect() as con, closing(con.cursor()) as c:
        for t in tables:
            try:
                r = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                counts[t] = int(r[0] or 0)
            except Exception:
                counts[t] = 0
        for t in tables:
            try:
                c.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        # сброс автонумерации (не обязателен, но удобно)
        try:
            c.execute("DELETE FROM sqlite_sequence")
        except Exception:
            pass
        con.commit()
    return counts

# -----------------------------
# Роли
# -----------------------------

def _get_role(user_id: int) -> Optional[str]:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT role FROM user_roles WHERE user_id=?", (user_id,)).fetchone()
        return r[0] if r else None

def _norm_username(provided: Optional[str], user_id: Optional[int]=None) -> str:
    uname = (provided or "").lower().lstrip("@")
    if uname:
        return uname
    if user_id:
        u = get_user(user_id)
        uname = (u or {}).get("username") or ""
        return uname.lower().lstrip("@")
    return ""

def set_role(user_id: int, role: str, added_by: int):
    now = datetime.now().isoformat()
    role = role.strip().lower()
    with connect() as con, closing(con.cursor()) as c:
        c.execute("""
        INSERT INTO user_roles(user_id, role, added_by, added_at)
        VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, added_by=excluded.added_by, added_at=excluded.added_at
        """, (user_id, role, added_by, now))
        con.commit()

def clear_role(user_id: int, role: Optional[str] = None) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if role:
            cur = c.execute("DELETE FROM user_roles WHERE user_id=? AND role=?", (user_id, role))
        else:
            cur = c.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
        con.commit()
        return cur.rowcount > 0

def add_brigadier(user_id: int, username: Optional[str], full_name: Optional[str], added_by: int):
    now = datetime.now().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        c.execute("""
        INSERT INTO brigadiers(user_id, username, full_name, added_by, added_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, added_by=excluded.added_by, added_at=excluded.added_at
        """, (user_id, username, full_name, added_by, now))
        con.commit()

def remove_brigadier(user_id: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM brigadiers WHERE user_id=?", (user_id,))
        con.commit()
        return cur.rowcount > 0

# -----------------------------
# Списки пользователей/бригадиров (для админских клавиатур)
# -----------------------------

def _display_user(full_name: Optional[str], username: Optional[str], user_id: int) -> str:
    fn = (full_name or "").strip()
    un = (username or "").strip().lstrip("@")
    if fn and un:
        return f"{fn} (@{un})"
    if fn:
        return fn
    if un:
        return f"@{un}"
    return str(user_id)

def count_registered_users() -> int:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT COUNT(*) FROM users WHERE full_name IS NOT NULL AND TRIM(full_name)<>''").fetchone()
        return int(r[0] or 0)

def list_registered_users(limit: int, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            """
            SELECT user_id, full_name, username
            FROM users
            WHERE full_name IS NOT NULL AND TRIM(full_name)<>''
            ORDER BY LOWER(full_name) ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [{"user_id": r[0], "full_name": r[1], "username": r[2]} for r in rows]

def count_brigadiers_known() -> int:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT user_id FROM user_roles WHERE role='brigadier'
              UNION
              SELECT user_id FROM brigadiers
            )
            """
        ).fetchone()
        return int(r[0] or 0)

def list_brigadiers_known(limit: int, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            """
            SELECT t.user_id,
                   COALESCE(u.full_name, t.full_name) AS full_name,
                   COALESCE(u.username,  t.username)  AS username
            FROM (
              SELECT ur.user_id AS user_id, NULL AS full_name, NULL AS username
              FROM user_roles ur
              WHERE ur.role='brigadier'
              UNION
              SELECT b.user_id AS user_id, b.full_name AS full_name, b.username AS username
              FROM brigadiers b
            ) t
            LEFT JOIN users u ON u.user_id=t.user_id
            ORDER BY LOWER(COALESCE(u.full_name, t.full_name, '')) ASC, t.user_id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [{"user_id": r[0], "full_name": r[1], "username": r[2]} for r in rows]

def is_admin(message_or_query) -> bool:
    uid = message_or_query.from_user.id
    uname = _norm_username(message_or_query.from_user.username, uid)
    if uid in ADMIN_IDS:
        return True
    if uname and uname in ADMIN_USERNAMES:
        return True
    return False

def is_it(user_id: int, username: Optional[str]=None) -> bool:
    role = _get_role(user_id)
    uname = _norm_username(username, user_id)
    return (role == "it") or (user_id in IT_IDS) or (uname and uname in IT_USERNAMES)

def is_tim(user_id: int, username: Optional[str]=None) -> bool:
    role = _get_role(user_id)
    uname = _norm_username(username, user_id)
    return (role == "tim") or (user_id in TIM_IDS) or (uname and uname in TIM_USERNAMES)

def is_brigadier(user_id: int, username: Optional[str]=None) -> bool:
    uname = _norm_username(username, user_id)
    if _get_role(user_id) == "brigadier":
        return True
    if uname and uname in BRIG_USERNAMES:
        return True
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT 1 FROM brigadiers WHERE user_id=?", (user_id,)).fetchone()
        return bool(r)

def get_role_label(user_id: int) -> str:
    u = get_user(user_id) or {}
    uname = u.get("username")
    if (user_id in ADMIN_IDS) or (uname and uname.lower().lstrip("@") in ADMIN_USERNAMES):
        return "admin"
    if is_tim(user_id, uname):
        return "tim"
    if is_it(user_id, uname):
        return "it"
    if is_brigadier(user_id, uname):
        return "brigadier"
    return "user"

def list_activities(grp: str) -> List[str]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("SELECT name FROM activities WHERE grp=? ORDER BY name", (grp,)).fetchall()
        return [r[0] for r in rows]

def add_activity(grp: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("INSERT INTO activities(name, grp) VALUES(?,?)", (name, grp))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def list_crops() -> List[str]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("SELECT name FROM crops ORDER BY name").fetchall()
        return [r[0] for r in rows]

def add_crop(name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    # Убедимся, что таблица есть
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("INSERT INTO crops(name) VALUES(?)", (name,))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def remove_crop(name: str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM crops WHERE name=?", (name,))
        con.commit()
        return cur.rowcount > 0

def remove_activity(name: str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM activities WHERE name=?", (name,))
        con.commit()
        return cur.rowcount > 0

def list_locations(grp: str) -> List[str]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("SELECT name FROM locations WHERE grp=? ORDER BY name", (grp,)).fetchall()
        return [r[0] for r in rows]

def list_locations_rows(*, grp: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        if grp:
            rows = c.execute(
                "SELECT id, name, grp FROM locations WHERE grp=? ORDER BY name LIMIT ? OFFSET ?",
                (grp, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, name, grp FROM locations ORDER BY grp, name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [{"id": r[0], "name": r[1], "grp": r[2]} for r in rows]

def count_locations(*, grp: Optional[str] = None) -> int:
    with connect() as con, closing(con.cursor()) as c:
        if grp:
            r = c.execute("SELECT COUNT(*) FROM locations WHERE grp=?", (grp,)).fetchone()
        else:
            r = c.execute("SELECT COUNT(*) FROM locations").fetchone()
        return int(r[0] or 0)

def get_location_by_id(loc_id: int) -> Optional[dict]:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT id, name, grp FROM locations WHERE id=?", (loc_id,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "name": r[1], "grp": r[2]}

def update_location_name(loc_id: int, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            cur = c.execute("UPDATE locations SET name=? WHERE id=?", (new_name, loc_id))
            con.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def delete_location_by_id(loc_id: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM locations WHERE id=?", (loc_id,))
        con.commit()
        return cur.rowcount > 0

def list_activities_rows(*, grp: str, limit: int = 50, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            "SELECT id, name, grp FROM activities WHERE grp=? ORDER BY name LIMIT ? OFFSET ?",
            (grp, limit, offset),
        ).fetchall()
        return [{"id": r[0], "name": r[1], "grp": r[2]} for r in rows]

def count_activities(grp: str) -> int:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT COUNT(*) FROM activities WHERE grp=?", (grp,)).fetchone()
        return int(r[0] or 0)

def get_activity_by_id(act_id: int) -> Optional[dict]:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT id, name, grp FROM activities WHERE id=?", (act_id,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "name": r[1], "grp": r[2]}

def update_activity_name(act_id: int, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            cur = c.execute("UPDATE activities SET name=? WHERE id=?", (new_name, act_id))
            con.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def delete_activity_by_id(act_id: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM activities WHERE id=?", (act_id,))
        con.commit()
        return cur.rowcount > 0

def list_crops_rows(limit: int = 50, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
        rows = c.execute("SELECT rowid, name FROM crops ORDER BY name LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [{"id": r[0], "name": r[1]} for r in rows]

def count_crops() -> int:
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
        r = c.execute("SELECT COUNT(*) FROM crops").fetchone()
        return int(r[0] or 0)

def get_crop_by_rowid(crop_rowid: int) -> Optional[dict]:
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
        r = c.execute("SELECT rowid, name FROM crops WHERE rowid=?", (crop_rowid,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "name": r[1]}

def update_crop_name(crop_rowid: int, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
        try:
            cur = c.execute("UPDATE crops SET name=? WHERE rowid=?", (new_name, crop_rowid))
            con.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def delete_crop_by_rowid(crop_rowid: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS crops(name TEXT PRIMARY KEY)")
        cur = c.execute("DELETE FROM crops WHERE rowid=?", (crop_rowid,))
        con.commit()
        return cur.rowcount > 0

# -----------------------------
# Техника (типы техники + список конкретной техники)
# -----------------------------

def list_machine_kinds(limit: int = 50, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            "SELECT id, title, mode FROM machine_kinds ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [{"id": r[0], "title": r[1], "mode": r[2] or "list"} for r in rows]

def count_machine_kinds() -> int:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT COUNT(*) FROM machine_kinds").fetchone()
        return int(r[0] or 0)

def get_machine_kind(kind_id: int) -> Optional[dict]:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT id, title, mode FROM machine_kinds WHERE id=?", (kind_id,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "title": r[1], "mode": r[2] or "list"}

def add_machine_kind(title: str, mode: str = "list") -> bool:
    title = (title or "").strip()
    if not title:
        return False
    mode = (mode or "list").strip().lower()
    if mode not in ("list", "single"):
        mode = "list"
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("INSERT INTO machine_kinds(title, mode) VALUES(?,?)", (title, mode))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def delete_machine_kind(kind_id: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        # удаляем связанные элементы
        c.execute("DELETE FROM machine_items WHERE kind_id=?", (kind_id,))
        cur = c.execute("DELETE FROM machine_kinds WHERE id=?", (kind_id,))
        con.commit()
        return cur.rowcount > 0

def list_machine_items(kind_id: int, limit: int = 50, offset: int = 0) -> List[dict]:
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            "SELECT id, kind_id, name FROM machine_items WHERE kind_id=? ORDER BY name LIMIT ? OFFSET ?",
            (kind_id, limit, offset),
        ).fetchall()
        return [{"id": r[0], "kind_id": r[1], "name": r[2]} for r in rows]

def count_machine_items(kind_id: int) -> int:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT COUNT(*) FROM machine_items WHERE kind_id=?", (kind_id,)).fetchone()
        return int(r[0] or 0)

def get_machine_item(item_id: int) -> Optional[dict]:
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT id, kind_id, name FROM machine_items WHERE id=?", (item_id,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "kind_id": r[1], "name": r[2]}

def add_machine_item(kind_id: int, name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("INSERT INTO machine_items(kind_id, name) VALUES(?,?)", (kind_id, name))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def update_machine_item(item_id: int, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            cur = c.execute("UPDATE machine_items SET name=? WHERE id=?", (new_name, item_id))
            con.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def delete_machine_item(item_id: int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM machine_items WHERE id=?", (item_id,))
        con.commit()
        return cur.rowcount > 0

def add_location(grp: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    with connect() as con, closing(con.cursor()) as c:
        try:
            c.execute("INSERT INTO locations(name, grp) VALUES(?,?)", (name, grp))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

# -----------------------------
# Бригадир отчёты
# -----------------------------

def insert_brig_report(
    user_id: int,
    username: Optional[str],
    work_type: str,
    field: str,
    shift: str,
    rows: Optional[int],
    bags: Optional[int],
    workers: Optional[int],
    work_date: str,
):
    now = datetime.now().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        c.execute(
            """
            INSERT INTO brigadier_reports(user_id, username, work_type, field, shift, rows, bags, workers, work_date, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (user_id, username, work_type, field, shift, rows, bags, workers, work_date, now),
        )
        con.commit()

def fetch_brig_stats(user_id: int, start_date: date, end_date: date) -> dict:
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            """
            SELECT work_type, rows, bags, workers, work_date
            FROM brigadier_reports
            WHERE user_id=? AND work_date BETWEEN ? AND ?
            ORDER BY work_date DESC
            """,
            (user_id, start_iso, end_iso),
        ).fetchall()
    def norm_crop(w_type: str) -> str:
        base = (w_type or "").split("—", 1)[0].split("(", 1)[0].strip()
        return base or "—"

    def emoji_for(crop: str) -> str:
        c = (crop or "").lower()
        if c.startswith("кабач"):
            return "🥒"
        if c.startswith("карт"):
            return "🥔"
        if c.startswith("нет"):
            return "⭕"
        if c.startswith("навоз"):
            return "💩"
        return "🌱"

    stats = {
        "by_crop": {},   # crop -> {rows,bags,workers}
        "details": [],
    }
    for w_type, w_rows, w_bags, w_workers, w_date in rows:
        crop = norm_crop(w_type)
        entry = stats["by_crop"].setdefault(crop, {"rows": 0, "bags": 0, "workers": 0})
        entry["rows"] += (w_rows or 0)
        entry["bags"] += (w_bags or 0)
        entry["workers"] += (w_workers or 0)
        d_str = date.fromisoformat(w_date).strftime("%d.%m")
        stats["details"].append(f"{d_str} {emoji_for(crop)}: {w_rows or 0}р, {w_bags or 0}м, {w_workers or 0}чел")
    return stats

def remove_location(name: str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM locations WHERE name=?", (name,))
        con.commit()
        return cur.rowcount > 0

def insert_report(
    user_id:int,
    reg_name:str,
    username:str,
    location:str,
    loc_grp:str,
    activity:str,
    act_grp:str,
    work_date:str,
    hours:int,
    chat_id:int,
    machine_type: Optional[str] = None,
    machine_name: Optional[str] = None,
    crop: Optional[str] = None,
    trips: Optional[int] = None,
) -> int:
    now = datetime.now().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        c.execute("""
        INSERT INTO reports(created_at, user_id, reg_name, username, location, location_grp,
                            activity, activity_grp, work_date, hours, chat_id,
                            machine_type, machine_name, crop, trips)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            now, user_id, reg_name, username, location, loc_grp, activity, act_grp,
            work_date, hours, chat_id, machine_type, machine_name, crop, trips
        ))
        con.commit()
        return c.lastrowid

def get_report(report_id:int):
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute(
            """
            SELECT id, created_at, user_id, reg_name, username, location, location_grp,
                   activity, activity_grp, work_date, hours, chat_id,
                   machine_type, machine_name, crop, trips
            FROM reports WHERE id=?
            """,
            (report_id,)
        ).fetchone()
        if not r:
            return None
        return {
            "id": r[0], "created_at": r[1], "user_id": r[2], "reg_name": r[3], "username": r[4],
            "location": r[5], "location_grp": r[6], "activity": r[7], "activity_grp": r[8],
            "work_date": r[9], "hours": r[10], "chat_id": r[11],
            "machine_type": r[12], "machine_name": r[13], "crop": r[14], "trips": r[15],
        }

def stat_get_msg(report_id:int):
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT chat_id, thread_id, message_id, last_action FROM stat_msgs WHERE report_id=?", (report_id,)).fetchone()
        return (r[0], r[1], r[2], r[3]) if r else None

def stat_save_msg(report_id:int, chat_id:int, thread_id:int, message_id:int, last_action:str):
    with connect() as con, closing(con.cursor()) as c:
        c.execute("INSERT OR REPLACE INTO stat_msgs(report_id, chat_id, thread_id, message_id, last_action) VALUES(?,?,?,?,?)",
                  (report_id, chat_id, thread_id, message_id, last_action))
        con.commit()

def sum_hours_for_user_date(user_id:int, work_date:str, exclude_report_id: Optional[int] = None) -> int:
    with connect() as con, closing(con.cursor()) as c:
        if exclude_report_id:
            r = c.execute("SELECT COALESCE(SUM(hours),0) FROM reports WHERE user_id=? AND work_date=? AND id<>?",
                          (user_id, work_date, exclude_report_id)).fetchone()
        else:
            r = c.execute("SELECT COALESCE(SUM(hours),0) FROM reports WHERE user_id=? AND work_date=?",
                          (user_id, work_date)).fetchone()
        return int(r[0] or 0)

def user_recent_24h_reports(user_id:int) -> List[tuple]:
    cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT id, work_date, activity, location, hours, created_at, machine_type, machine_name, crop, trips
        FROM reports
        WHERE user_id=? AND created_at>=?
        ORDER BY created_at DESC
        """, (user_id, cutoff)).fetchall()
        return rows

def delete_report(report_id:int, user_id:int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        # Проверяем, существует ли отчет и что есть права на удаление.
        # Для админа — можно удалить любую запись.
        if _is_admin_user_id(user_id):
            report = c.execute("SELECT id FROM reports WHERE id=?", (report_id,)).fetchone()
        else:
            report = c.execute("SELECT id FROM reports WHERE id=? AND user_id=?", (report_id, user_id)).fetchone()
        if not report:
            return False
        
        # Удаляем отчет
        if _is_admin_user_id(user_id):
            cur = c.execute("DELETE FROM reports WHERE id=?", (report_id,))
        else:
            cur = c.execute("DELETE FROM reports WHERE id=? AND user_id=?", (report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_hours(report_id:int, user_id:int, new_hours:int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute("UPDATE reports SET hours=? WHERE id=?", (new_hours, report_id))
        else:
            cur = c.execute("UPDATE reports SET hours=? WHERE id=? AND user_id=?", (new_hours, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_location(report_id:int, user_id:int, new_location:str, new_location_grp:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute(
                "UPDATE reports SET location=?, location_grp=? WHERE id=?",
                (new_location, new_location_grp, report_id),
            )
        else:
            cur = c.execute(
                "UPDATE reports SET location=?, location_grp=? WHERE id=? AND user_id=?",
                (new_location, new_location_grp, report_id, user_id),
            )
        con.commit()
        return cur.rowcount > 0

def update_report_activity(report_id:int, user_id:int, new_activity:str, new_activity_grp:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute(
                "UPDATE reports SET activity=?, activity_grp=? WHERE id=?",
                (new_activity, new_activity_grp, report_id),
            )
        else:
            cur = c.execute(
                "UPDATE reports SET activity=?, activity_grp=? WHERE id=? AND user_id=?",
                (new_activity, new_activity_grp, report_id, user_id),
            )
        con.commit()
        return cur.rowcount > 0

def update_report_machine(report_id:int, user_id:int, machine_type:Optional[str], machine_name:Optional[str]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute(
                "UPDATE reports SET machine_type=?, machine_name=? WHERE id=?",
                (machine_type, machine_name, report_id),
            )
        else:
            cur = c.execute(
                "UPDATE reports SET machine_type=?, machine_name=? WHERE id=? AND user_id=?",
                (machine_type, machine_name, report_id, user_id),
            )
        con.commit()
        return cur.rowcount > 0

def update_report_crop(report_id:int, user_id:int, crop:Optional[str]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute("UPDATE reports SET crop=? WHERE id=?", (crop, report_id))
        else:
            cur = c.execute("UPDATE reports SET crop=? WHERE id=? AND user_id=?", (crop, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_trips(report_id:int, user_id:int, trips:Optional[int]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute("UPDATE reports SET trips=? WHERE id=?", (trips, report_id))
        else:
            cur = c.execute("UPDATE reports SET trips=? WHERE id=? AND user_id=?", (trips, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_date(report_id:int, user_id:int, new_date:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        if _is_admin_user_id(user_id):
            cur = c.execute("UPDATE reports SET work_date=? WHERE id=?", (new_date, report_id))
        else:
            cur = c.execute("UPDATE reports SET work_date=? WHERE id=? AND user_id=?", (new_date, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def fetch_stats_today_all():
    today = date.today().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT r.user_id, u.full_name, u.username, r.location, r.activity, SUM(r.hours) as h
        FROM reports r
        LEFT JOIN users u ON u.user_id=r.user_id
        WHERE r.work_date=?
        GROUP BY r.user_id, r.location, r.activity
        ORDER BY u.full_name, r.location, r.activity
        """, (today,)).fetchall()
        return rows

def fetch_stats_range_for_user(user_id:int, start_date:str, end_date:str):
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT work_date, location, activity, SUM(hours) as h
        FROM reports
        WHERE user_id=? AND work_date BETWEEN ? AND ?
        GROUP BY work_date, location, activity
        ORDER BY work_date DESC
        """, (user_id, start_date, end_date)).fetchall()
        return rows

def fetch_stats_month_for_user(user_id:int):
    today = date.today()
    start = today.replace(day=1).isoformat()
    # следующий месяц
    if today.month == 12:
        end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    end = end_date.isoformat()
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT id, work_date, activity, location, hours, machine_type, machine_name, crop, trips
        FROM reports
        WHERE user_id=? AND work_date BETWEEN ? AND ?
        ORDER BY work_date DESC, created_at DESC
        """, (user_id, start, end)).fetchall()
        return rows

def fetch_stats_range_all(start_date:str, end_date:str):
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT u.full_name, u.username, work_date, location, activity, SUM(hours) as h
        FROM reports r
        LEFT JOIN users u ON u.user_id=r.user_id
        WHERE work_date BETWEEN ? AND ?
        GROUP BY u.full_name, u.username, work_date, location, activity
        ORDER BY work_date DESC, u.full_name
        """, (start_date, end_date)).fetchall()
        return rows

def fetch_stats_range_all_with_uid(start_date: str, end_date: str):
    """
    Для админской статистики/редактирования: как fetch_stats_range_all, но с user_id.
    """
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT r.user_id, u.full_name, u.username, work_date, location, activity, SUM(hours) as h
        FROM reports r
        LEFT JOIN users u ON u.user_id=r.user_id
        WHERE work_date BETWEEN ? AND ?
        GROUP BY r.user_id, u.full_name, u.username, work_date, location, activity
        ORDER BY work_date DESC, u.full_name
        """, (start_date, end_date)).fetchall()
        return rows

def fetch_reports_for_user_range(user_id: int, start_date: str, end_date: str) -> List[tuple]:
    """
    Для админа: список конкретных записей (с id) за период, чтобы можно было изменить/удалить.
    """
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT id, work_date, activity, location, hours, created_at, machine_type, machine_name, crop, trips
        FROM reports
        WHERE user_id=? AND work_date BETWEEN ? AND ?
        ORDER BY work_date DESC, created_at DESC
        """, (user_id, start_date, end_date)).fetchall()
        return rows

def fetch_users_with_reports_range(start_date: str, end_date: str) -> List[tuple]:
    """
    Для админского редактирования: список пользователей, у которых есть записи за период.
    returns: (user_id, full_name, username)
    """
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute(
            """
            SELECT r.user_id,
                   COALESCE(u.full_name, '') AS full_name,
                   COALESCE(u.username,  '') AS username
            FROM reports r
            LEFT JOIN users u ON u.user_id=r.user_id
            WHERE r.work_date BETWEEN ? AND ?
            GROUP BY r.user_id
            ORDER BY LOWER(COALESCE(u.full_name, '')) ASC, r.user_id ASC
            """,
            (start_date, end_date),
        ).fetchall()
        return rows

# -----------------------------
# Google Sheets API
# -----------------------------

def get_google_credentials():
    """Получить учетные данные Google OAuth"""
    creds = None
    if TOKEN_JSON_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON_PATH), GOOGLE_SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(OAUTH_CLIENT_JSON).exists():
                logging.error(f"OAuth client file not found: {OAUTH_CLIENT_JSON}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT_JSON, GOOGLE_SCOPES)
            try:
                creds = flow.run_local_server(port=0)
            except Exception:
                creds = flow.run_console()
        TOKEN_JSON_PATH.write_text(creds.to_json(), encoding="utf-8")
    
    return creds

def retry_google_api_call(func, max_retries=3, delay=1):
    """Повторные попытки вызова Google API с обработкой SSL ошибок"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_msg = str(e).lower()
            if any(ssl_error in error_msg for ssl_error in ['ssl', 'eof', 'protocol', 'connection']):
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(f"SSL error on attempt {attempt + 1}, retrying in {wait_time:.1f}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"SSL error after {max_retries} attempts: {e}")
                    raise
            else:
                # Не SSL ошибка - не повторяем
                raise
    return None

def _drive_escape_q(s: str) -> str:
    # Escape single quotes for Drive query strings
    return (s or "").replace("'", "\\'")

def _drive_find_spreadsheet_in_folder(drive, *, folder_id: str, name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Ищет существующую Google Sheet по имени в указанной папке Drive.
    Возвращает (spreadsheet_id, webViewLink) или (None, None).
    """
    if not folder_id or not name:
        return None, None

    q = (
        "mimeType='application/vnd.google-apps.spreadsheet' "
        f"and name='{_drive_escape_q(name)}' "
        f"and '{folder_id}' in parents "
        "and trashed=false"
    )

    def _list():
        return drive.files().list(
            q=q,
            fields="files(id, webViewLink, createdTime)",
            pageSize=20,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

    res = retry_google_api_call(_list)
    files = (res or {}).get("files") or []
    if not files:
        return None, None

    # If duplicates exist, prefer the newest.
    files_sorted = sorted(files, key=lambda f: (f.get("createdTime") or ""), reverse=True)
    f0 = files_sorted[0] or {}
    sid = f0.get("id")
    link = f0.get("webViewLink")
    if sid and not link:
        def _get():
            return drive.files().get(fileId=sid, fields="webViewLink", supportsAllDrives=True).execute()
        got = retry_google_api_call(_get) or {}
        link = got.get("webViewLink")
    return sid, link

def get_or_create_monthly_sheet(year: int, month: int):
    """Получить или создать таблицу для месяца"""
    with connect() as con, closing(con.cursor()) as c:
        # Проверяем, есть ли уже таблица для этого месяца
        row = c.execute(
            "SELECT spreadsheet_id, sheet_url FROM monthly_sheets WHERE year=? AND month=?",
            (year, month)
        ).fetchone()
        
        if row:
            return row[0], row[1]
        
        # Создаем новую таблицу
        try:
            creds = get_google_credentials()
            if not creds:
                return None, None
            
            drive = build("drive", "v3", credentials=creds)
            sheets = build("sheets", "v4", credentials=creds)
            
            # Название таблицы с месяцем и годом (как в WhatsApp-таблицах)
            month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
            sheet_name = f"{EXPORT_PREFIX} - {month_names[month]} {year}"

            # Если таблица уже создана (например, WhatsApp-ботом), переиспользуем её.
            if DRIVE_FOLDER_ID:
                existing_id, existing_url = _drive_find_spreadsheet_in_folder(
                    drive, folder_id=DRIVE_FOLDER_ID, name=sheet_name
                )
                if existing_id and existing_url:
                    c.execute(
                        "INSERT INTO monthly_sheets(year, month, spreadsheet_id, sheet_url, created_at) VALUES(?,?,?,?,?)",
                        (year, month, existing_id, existing_url, datetime.now().isoformat()),
                    )
                    con.commit()
                    logging.info(f"Reused existing sheet for {year}-{month:02d}: {existing_url}")
                    return existing_id, existing_url
            
            # Создаем таблицу с повторными попытками
            file_metadata = {
                "name": sheet_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }
            if DRIVE_FOLDER_ID:
                file_metadata["parents"] = [DRIVE_FOLDER_ID]
            
            def create_file():
                return drive.files().create(
                    body=file_metadata,
                    fields="id, webViewLink"
                ).execute()
            
            file = retry_google_api_call(create_file)
            
            spreadsheet_id = file["id"]
            sheet_url = file["webViewLink"]
            
            # Добавляем заголовки (формат как на скринах: 7 колонок)
            headers = [[
                "Дата создания",
                "User ID",
                "Имя",
                "Локация",
                "Вид работы",
                "Дата работы",
                "Часы",
            ]]
            
            def update_headers():
                return sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range="A1:G1",
                    valueInputOption="RAW",
                    body={"values": headers}
                ).execute()
            
            retry_google_api_call(update_headers)
            
            # Форматирование заголовков (жирный шрифт) с повторными попытками
            requests = [{
                "repeatCell": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 0,
                        "endRowIndex": 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True}
                        }
                    },
                    "fields": "userEnteredFormat.textFormat.bold"
                }
            }]
            
            def format_headers():
                return sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": requests}
                ).execute()
            
            retry_google_api_call(format_headers)
            
            # Сохраняем в БД
            c.execute(
                "INSERT INTO monthly_sheets(year, month, spreadsheet_id, sheet_url, created_at) VALUES(?,?,?,?,?)",
                (year, month, spreadsheet_id, sheet_url, datetime.now().isoformat())
            )
            con.commit()
            
            logging.info(f"Created new sheet for {year}-{month:02d}: {sheet_url}")
            return spreadsheet_id, sheet_url
            
        except HttpError as e:
            logging.error(f"Google API error: {e}")
            return None, None

def get_or_create_brig_monthly_sheet(year: int, month: int):
    """Получить или создать таблицу бригадиров для месяца (в BRIGADIER_FOLDER_ID)."""
    if not BRIGADIER_FOLDER_ID:
        return None, None
    with connect() as con, closing(con.cursor()) as c:
        row = c.execute(
            "SELECT spreadsheet_id, sheet_url FROM brig_monthly_sheets WHERE year=? AND month=?",
            (year, month)
        ).fetchone()
        if row:
            return row[0], row[1]

        try:
            creds = get_google_credentials()
            if not creds:
                return None, None

            drive = build("drive", "v3", credentials=creds)
            sheets = build("sheets", "v4", credentials=creds)

            month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                           "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
            sheet_name = f"{BRIG_EXPORT_PREFIX} - {month_names[month]} {year}"

            # Если таблица уже создана (например, WhatsApp-ботом), переиспользуем её.
            existing_id, existing_url = _drive_find_spreadsheet_in_folder(
                drive, folder_id=BRIGADIER_FOLDER_ID, name=sheet_name
            )
            if existing_id and existing_url:
                c.execute(
                    "INSERT INTO brig_monthly_sheets(year, month, spreadsheet_id, sheet_url, created_at) VALUES(?,?,?,?,?)",
                    (year, month, existing_id, existing_url, datetime.now().isoformat()),
                )
                con.commit()
                logging.info(f"Reused existing brig sheet for {year}-{month:02d}: {existing_url}")
                return existing_id, existing_url

            file_metadata = {
                "name": sheet_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [BRIGADIER_FOLDER_ID],
            }

            def create_file():
                return drive.files().create(
                    body=file_metadata,
                    fields="id, webViewLink"
                ).execute()

            file = retry_google_api_call(create_file)
            spreadsheet_id = file["id"]
            sheet_url = file["webViewLink"]

            headers = [[
                "Дата создания",
                "User ID",
                "Имя",
                "Культура",
                "Поле",
                "Смена",
                "Рядов",
                "Мешков",
                "Людей",
                "Дата работы",
            ]]

            def update_headers():
                return sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range="A1:J1",
                    valueInputOption="RAW",
                    body={"values": headers}
                ).execute()

            retry_google_api_call(update_headers)

            # форматирование заголовков
            requests = [{
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold"
                }
            }]

            def format_headers():
                return sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": requests}
                ).execute()

            retry_google_api_call(format_headers)

            c.execute(
                "INSERT INTO brig_monthly_sheets(year, month, spreadsheet_id, sheet_url, created_at) VALUES(?,?,?,?,?)",
                (year, month, spreadsheet_id, sheet_url, datetime.now().isoformat())
            )
            con.commit()
            logging.info(f"Created brig sheet for {year}-{month:02d}: {sheet_url}")
            return spreadsheet_id, sheet_url

        except HttpError as e:
            logging.error(f"Google API error (brig sheet): {e}")
            return None, None
        except Exception as e:
            logging.error(f"Error creating brig sheet: {e}")
            return None, None
        except Exception as e:
            logging.error(f"Error creating sheet: {e}")
            return None, None

def get_reports_to_export():
    """Получить список отчетов для экспорта (новые, измененные, удаленные)"""
    with connect() as con, closing(con.cursor()) as c:
        # Получаем все отчеты, которые нужно экспортировать
        rows = c.execute("""
        SELECT r.id, r.created_at, COALESCE(u.phone, '') AS phone, r.reg_name, r.location, r.activity, r.work_date, r.hours,
               ge.report_id as is_exported, ge.row_number, ge.last_updated
        FROM reports r
        LEFT JOIN users u ON u.user_id = r.user_id
        LEFT JOIN google_exports ge ON r.id = ge.report_id
        ORDER BY r.work_date, r.created_at
        """).fetchall()
        return rows

def get_deleted_reports():
    """Получить список удаленных отчетов, которые нужно удалить из таблиц"""
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT ge.report_id, ge.spreadsheet_id, ge.row_number
        FROM google_exports ge
        LEFT JOIN reports r ON ge.report_id = r.id
        WHERE r.id IS NULL
        """).fetchall()
        return rows

def get_brig_reports_to_export():
    """Получить список бригадирских отчетов для экспорта (новые/измененные/удаленные)."""
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT br.id,
               br.created_at,
               COALESCE(u.phone, '') AS phone,
               COALESCE(u.full_name, br.username, '') AS name,
               br.work_type,
               br.field,
               br.shift,
               br.rows,
               br.bags,
               br.workers,
               br.work_date,
               ge.brig_report_id as is_exported,
               ge.row_number,
               ge.last_updated
        FROM brigadier_reports br
        LEFT JOIN users u ON u.user_id = br.user_id
        LEFT JOIN brig_google_exports ge ON br.id = ge.brig_report_id
        ORDER BY br.work_date, br.created_at
        """).fetchall()
        return rows

def get_deleted_brig_reports():
    """Удаленные бригадирские отчеты, которые нужно удалить из Google Sheets."""
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT ge.brig_report_id, ge.spreadsheet_id, ge.row_number
        FROM brig_google_exports ge
        LEFT JOIN brigadier_reports br ON ge.brig_report_id = br.id
        WHERE br.id IS NULL
        """).fetchall()
        return rows

def export_brigadier_reports_to_sheets():
    """
    Экспортировать бригадирские отчёты в Google Sheets (в BRIGADIER_FOLDER_ID).
    Не использует DRIVE_FOLDER_ID и не пишет в общую папку.
    """
    if not BRIGADIER_FOLDER_ID:
        return 0, "BRIGADIER_FOLDER_ID не задан — экспорт бригадиров выключен"
    try:
        creds = get_google_credentials()
        if not creds:
            return 0, "Ошибка авторизации Google"

        sheets_service = build("sheets", "v4", credentials=creds)
        drive = build("drive", "v3", credentials=creds)

        all_reports = get_brig_reports_to_export()
        deleted_reports = get_deleted_brig_reports()

        if not all_reports and not deleted_reports:
            return 0, "Нет бригадирских отчетов для экспорта"

        reports_by_month = {}
        for row in all_reports:
            (rid, created_at, phone, name, work_type, field, shift, rows, bags, workers,
             work_date, is_exported, row_number, last_updated) = row
            d = datetime.fromisoformat(work_date)
            key = (d.year, d.month)
            reports_by_month.setdefault(key, []).append(
                (rid, created_at, phone, name, work_type, field, shift, rows, bags, workers,
                 work_date, is_exported, row_number, last_updated)
            )

        total_exported = 0
        total_updated = 0
        total_deleted = 0

        # удаленные
        # Важно: deleteDimension сдвигает строки вверх, поэтому корректируем row_number в БД.
        deleted_by_sheet: Dict[str, List[Tuple[int, int]]] = {}
        for report_id, spreadsheet_id, row_number in deleted_reports:
            if not spreadsheet_id or not row_number:
                continue
            deleted_by_sheet.setdefault(spreadsheet_id, []).append((int(report_id), int(row_number)))

        for spreadsheet_id, items in deleted_by_sheet.items():
            items.sort(key=lambda x: x[1], reverse=True)
            for report_id, row_number in items:
                try:
                    def delete_row():
                        return sheets_service.spreadsheets().batchUpdate(
                            spreadsheetId=spreadsheet_id,
                            body={"requests": [{
                                "deleteDimension": {
                                    "range": {
                                        "sheetId": 0,
                                        "dimension": "ROWS",
                                        "startIndex": row_number - 1,
                                        "endIndex": row_number
                                    }
                                }
                            }]}
                        ).execute()

                    retry_google_api_call(delete_row)
                    with connect() as con, closing(con.cursor()) as c:
                        c.execute("DELETE FROM brig_google_exports WHERE brig_report_id=?", (report_id,))
                        c.execute(
                            "UPDATE brig_google_exports SET row_number = row_number - 1 "
                            "WHERE spreadsheet_id=? AND row_number>?",
                            (spreadsheet_id, row_number),
                        )
                        con.commit()
                    total_deleted += 1
                except Exception as e:
                    logging.error(f"Error deleting brig report {report_id}: {e}")

        for (year, month), reports in reports_by_month.items():
            spreadsheet_id, sheet_url = get_or_create_brig_monthly_sheet(year, month)
            if not spreadsheet_id:
                continue

            # обновляем имя файла (стабильно)
            try:
                month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                               "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
                new_name = f"{BRIG_EXPORT_PREFIX} - {month_names[month]} {year}"

                def update_sheet_name():
                    return drive.files().update(fileId=spreadsheet_id, body={"name": new_name}).execute()

                retry_google_api_call(update_sheet_name)
            except Exception:
                pass

            def get_existing_data():
                return sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="A:J"
                ).execute()

            try:
                result = retry_google_api_call(get_existing_data)
                existing_values = result.get("values", []) if result else []
                next_row = len(existing_values) + 1
            except Exception:
                next_row = 2

            for (rid, created_at, phone, name, work_type, field, shift, rows, bags, workers,
                 work_date, is_exported, row_number, last_updated) in reports:
                values = [
                    format_dt_minute(created_at),
                    phone,
                    name,
                    work_type,
                    field,
                    shift,
                    rows if rows is not None else "",
                    bags if bags is not None else "",
                    workers if workers is not None else "",
                    work_date,
                ]

                if is_exported and row_number:
                    def update_record():
                        return sheets_service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"A{row_number}:J{row_number}",
                            valueInputOption="RAW",
                            body={"values": [values]}
                        ).execute()
                    try:
                        retry_google_api_call(update_record)
                        now = datetime.now().isoformat()
                        with connect() as con, closing(con.cursor()) as c:
                            c.execute(
                                "UPDATE brig_google_exports SET last_updated=? WHERE brig_report_id=?",
                                (now, rid)
                            )
                            con.commit()
                        total_updated += 1
                    except Exception as e:
                        logging.error(f"Error updating brig report {rid}: {e}")
                else:
                    def add_record():
                        return sheets_service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"A{next_row}:J{next_row}",
                            valueInputOption="RAW",
                            body={"values": [values]}
                        ).execute()
                    try:
                        retry_google_api_call(add_record)
                        now = datetime.now().isoformat()
                        with connect() as con, closing(con.cursor()) as c:
                            c.execute(
                                "INSERT INTO brig_google_exports(brig_report_id, spreadsheet_id, sheet_name, row_number, exported_at, last_updated) "
                                "VALUES(?,?,?,?,?,?)",
                                (rid, spreadsheet_id, f"{year}-{month:02d}", next_row, now, now)
                            )
                            con.commit()
                        total_exported += 1
                        next_row += 1
                    except Exception as e:
                        logging.error(f"Error adding brig report {rid}: {e}")

        messages = []
        if total_exported > 0:
            messages.append(f"Добавлено: {total_exported}")
        if total_updated > 0:
            messages.append(f"Обновлено: {total_updated}")
        if total_deleted > 0:
            messages.append(f"Удалено: {total_deleted}")

        if messages:
            return total_exported + total_updated + total_deleted, "Бригадиры: " + ", ".join(messages)
        return 0, "Бригадиры: нет изменений"

    except HttpError as e:
        logging.error(f"Google API error during brig export: {e}")
        return 0, f"Ошибка Google API (бригадиры): {str(e)}"
    except Exception as e:
        logging.error(f"Error during brig export: {e}")
        return 0, f"Ошибка экспорта (бригадиры): {str(e)}"

def export_reports_to_sheets():
    """Экспортировать отчеты в Google Sheets с учетом изменений и удалений"""
    try:
        creds = get_google_credentials()
        if not creds:
            return 0, "Ошибка авторизации Google"
        
        sheets_service = build("sheets", "v4", credentials=creds)
        drive = build("drive", "v3", credentials=creds)
        
        # Получаем все отчеты для экспорта
        all_reports = get_reports_to_export()
        deleted_reports = get_deleted_reports()
        
        if not all_reports and not deleted_reports:
            logging.info("No reports to export")
            return 0, "Нет отчетов для экспорта"
        
        # Группируем отчеты по месяцам
        reports_by_month = {}
        for row in all_reports:
            report_id, created_at, phone, name, location, activity, work_date, hours, is_exported, row_number, last_updated = row
            d = datetime.fromisoformat(work_date)
            key = (d.year, d.month)
            if key not in reports_by_month:
                reports_by_month[key] = []
            reports_by_month[key].append((report_id, created_at, phone, name, location, activity, work_date, hours, is_exported, row_number, last_updated))
        
        total_exported = 0
        total_updated = 0
        total_deleted = 0
        
        # Обрабатываем удаленные записи
        # Важно: при deleteDimension все строки ниже "поднимаются" на 1,
        # поэтому нужно корректировать сохранённые row_number в БД.
        deleted_by_sheet: Dict[str, List[Tuple[int, int]]] = {}
        for report_id, spreadsheet_id, row_number in deleted_reports:
            if not spreadsheet_id or not row_number:
                continue
            deleted_by_sheet.setdefault(spreadsheet_id, []).append((int(report_id), int(row_number)))

        for spreadsheet_id, items in deleted_by_sheet.items():
            # Удаляем снизу вверх, чтобы индексы не "ехали" при множественных удалениях
            items.sort(key=lambda x: x[1], reverse=True)
            for report_id, row_number in items:
                try:
                    # Удаляем строку из таблицы с повторными попытками
                    def delete_row():
                        return sheets_service.spreadsheets().batchUpdate(
                            spreadsheetId=spreadsheet_id,
                            body={
                                "requests": [{
                                    "deleteDimension": {
                                        "range": {
                                            "sheetId": 0,
                                            "dimension": "ROWS",
                                            "startIndex": row_number - 1,
                                            "endIndex": row_number
                                        }
                                    }
                                }]
                            }
                        ).execute()
                    
                    retry_google_api_call(delete_row)
                    
                    # Удаляем запись из БД
                    with connect() as con, closing(con.cursor()) as c:
                        c.execute("DELETE FROM google_exports WHERE report_id=?", (report_id,))
                        # Сдвигаем номера строк для оставшихся записей в этом spreadsheet
                        c.execute(
                            "UPDATE google_exports SET row_number = row_number - 1 "
                            "WHERE spreadsheet_id=? AND row_number>? ",
                            (spreadsheet_id, row_number),
                        )
                        con.commit()
                    
                    total_deleted += 1
                    logging.info(f"Deleted report {report_id} from sheet")
                    
                except Exception as e:
                    logging.error(f"Error deleting report {report_id}: {e}")
        
        # Экспортируем каждую группу по месяцам
        for (year, month), reports in reports_by_month.items():
            spreadsheet_id, sheet_url = get_or_create_monthly_sheet(year, month)
            
            if not spreadsheet_id:
                logging.error(f"Failed to get/create sheet for {year}-{month}")
                continue
            
            # Обновляем название таблицы с текущей датой
            try:
                month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                              "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
                new_name = f"{EXPORT_PREFIX} - {month_names[month]} {year}"
                
                def update_sheet_name():
                    return drive.files().update(
                        fileId=spreadsheet_id,
                        body={"name": new_name}
                    ).execute()
                
                retry_google_api_call(update_sheet_name)
                logging.info(f"Updated sheet name to: {new_name}")
                
            except Exception as e:
                logging.warning(f"Failed to update sheet name: {e}")
            
            # Получаем текущие данные из таблицы с повторными попытками
            def get_existing_data():
                return sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="A:G"
                ).execute()
            
            try:
                result = retry_google_api_call(get_existing_data)
                existing_values = result.get("values", []) if result else []
                next_row = len(existing_values) + 1
            except Exception:
                next_row = 2  # Начинаем со второй строки (после заголовков)
            
            # Обрабатываем отчеты
            for report_id, created_at, phone, name, location, activity, work_date, hours, is_exported, row_number, last_updated in reports:
                # phone (UserID) — телефон. Если не указан, оставляем пустым (но в логах это будет видно).
                values = [format_dt_minute(created_at), phone, name, location, activity, work_date, hours]
                
                if is_exported and row_number:
                    # Обновляем существующую запись с повторными попытками
                    def update_record():
                        return sheets_service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"A{row_number}:G{row_number}",
                            valueInputOption="RAW",
                            body={"values": [values]}
                        ).execute()
                    
                    try:
                        retry_google_api_call(update_record)
                        
                        # Обновляем время последнего изменения в БД
                        now = datetime.now().isoformat()
                        with connect() as con, closing(con.cursor()) as c:
                            c.execute(
                                "UPDATE google_exports SET last_updated=? WHERE report_id=?",
                                (now, report_id)
                            )
                            con.commit()
                        
                        total_updated += 1
                        logging.info(f"Updated report {report_id} in sheet")
                        
                    except Exception as e:
                        logging.error(f"Error updating report {report_id}: {e}")
                else:
                    # Добавляем новую запись с повторными попытками
                    def add_record():
                        return sheets_service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"A{next_row}:G{next_row}",
                            valueInputOption="RAW",
                            body={"values": [values]}
                        ).execute()
                    
                    try:
                        retry_google_api_call(add_record)
                        
                        # Записываем информацию об экспорте в БД
                        now = datetime.now().isoformat()
                        with connect() as con, closing(con.cursor()) as c:
                            c.execute(
                                "INSERT INTO google_exports(report_id, spreadsheet_id, sheet_name, row_number, exported_at, last_updated) VALUES(?,?,?,?,?,?)",
                                (report_id, spreadsheet_id, f"{year}-{month:02d}", next_row, now, now)
                            )
                            con.commit()
                        
                        total_exported += 1
                        next_row += 1
                        logging.info(f"Added new report {report_id} to sheet")
                        
                    except Exception as e:
                        logging.error(f"Error adding report {report_id}: {e}")
        
        # Формируем сообщение о результатах
        messages = []
        if total_exported > 0:
            messages.append(f"Добавлено: {total_exported}")
        if total_updated > 0:
            messages.append(f"Обновлено: {total_updated}")
        if total_deleted > 0:
            messages.append(f"Удалено: {total_deleted}")
        
        if messages:
            result_message = "Экспорт завершен. " + ", ".join(messages)
        else:
            result_message = "Нет изменений для экспорта"
        
        return total_exported + total_updated + total_deleted, result_message
        
    except HttpError as e:
        logging.error(f"Google API error during export: {e}")
        return 0, f"Ошибка Google API: {str(e)}"
    except Exception as e:
        logging.error(f"Error during export: {e}")
        return 0, f"Ошибка экспорта: {str(e)}"

def check_and_create_next_month_sheet():
    """Проверить и создать таблицу для следующего месяца за 3 дня до конца текущего"""
    today = date.today()
    # Получаем последний день текущего месяца
    last_day = calendar.monthrange(today.year, today.month)[1]
    days_until_end = last_day - today.day
    
    if days_until_end <= 3:
        # Вычисляем следующий месяц
        if today.month == 12:
            next_year, next_month = today.year + 1, 1
        else:
            next_year, next_month = today.year, today.month + 1
        
        # Проверяем, создана ли уже таблица для следующего месяца
        with connect() as con, closing(con.cursor()) as c:
            row = c.execute(
                "SELECT spreadsheet_id FROM monthly_sheets WHERE year=? AND month=?",
                (next_year, next_month)
            ).fetchone()
            
            if not row:
                logging.info(f"Creating sheet for next month: {next_year}-{next_month:02d}")
                spreadsheet_id, sheet_url = get_or_create_monthly_sheet(next_year, next_month)
                if spreadsheet_id:
                    return True, f"Создана таблица для {next_year}-{next_month:02d}: {sheet_url}"
                else:
                    return False, "Ошибка создания таблицы"
    
    return False, "Не требуется создание таблицы"

# -----------------------------
# FSM
# -----------------------------

class NameFSM(StatesGroup):
    waiting_name = State()

class PhoneFSM(StatesGroup):
    waiting_phone_text = State()
    waiting_phone_contact = State()

class WorkFSM(StatesGroup):
    pick_group = State()
    pick_activity = State()
    pick_loc_group = State()
    pick_location = State()
    pick_date = State()
    pick_hours = State()

class OtdFSM(StatesGroup):
    pick_date = State()
    pick_hours = State()
    pick_type = State()
    pick_machine_type = State()
    pick_machine = State()
    pick_machine_custom = State()
    pick_activity = State()
    pick_activity_custom = State()
    pick_location = State()
    pick_crop = State()
    pick_crop_custom = State()
    pick_trips = State()
    confirm = State()

class AdminFSM(StatesGroup):
    add_group = State()
    add_name = State()
    del_group = State()
    del_pick = State()
    add_brig_id = State()
    del_brig_id = State()
    edit_name = State()
    edit_confirm = State()

class EditFSM(StatesGroup):
    waiting_field_numbers = State()
    waiting_new_hours = State()
    waiting_new_location = State()
    waiting_new_activity = State()
    waiting_new_crop = State()
    waiting_new_trips = State()
    waiting_new_date = State()
    waiting_new_machine = State()

class BrigFSM(StatesGroup):
    pick_date = State()
    pick_hours = State()
    pick_shift = State()
    pick_mode = State()
    pick_crop = State()
    pick_crop_custom = State()
    pick_activity = State()
    pick_activity_custom = State()
    pick_machine_kind = State()
    pick_machine_name = State()
    pick_machine_name_custom = State()
    pick_machine_activity = State()
    pick_machine_activity_custom = State()
    pick_machine_crop = State()
    pick_machine_crop_custom = State()
    pick_kamaz_crop = State()
    pick_kamaz_crop_custom = State()
    pick_kamaz_trips = State()
    pick_kamaz_load = State()
    pick_kamaz_load_custom = State()
    pick_field = State()
    pick_rows = State()
    pick_bags = State()
    pick_workers = State()
    confirm = State()

# -----------------------------
# Вспомогалки: одно-сообщение и проверки
# -----------------------------

def _ui_main_menu_text(user_id: int) -> str:
    """
    Текст статичного главного меню (1-е сообщение).
    Делаем "как было" и с разным текстом по ролям.
    """
    u = get_user(user_id) or {}
    name = (u.get("full_name") or "—").strip() or "—"
    role = get_role_label(user_id)
    role_suffix = " (бригадир)" if role == "brigadier" else (" (админ)" if role == "admin" else "")
    text = (
        f"👋 Привет, <b>{name}</b>{role_suffix}!\n\n"
        "Выберите действие:"
    )
    if role in ("it", "admin"):
        text += (
            "\n\nДоступные команды:\n"
            "• admin — админ-меню\n"
            "• brig — меню бригадиров\n"
            "• it — IT-меню\n"
            "• menu — основное меню"
        )
    return text

# быстрый кэш ui_state (chat_id, user_id) -> {"menu": int|None, "content": int|None}
_ui_cache: Dict[Tuple[int, int], dict] = {}

# UI locks: prevent races when multiple callback updates are processed concurrently.
_ui_locks: Dict[Tuple[int, int], asyncio.Lock] = {}

def _ui_get_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    key = (chat_id, user_id)
    lock = _ui_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _ui_locks[key] = lock
    return lock

# sentinel to distinguish "not provided" from "set NULL"
_UNSET = object()

async def _ui_try_delete_user_message(message: Message) -> None:
    """
    Best-effort cleanup: tries to delete user's text input to keep the chat cleaner.
    Safe to call anywhere; failures are ignored.
    """
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    except Exception:
        pass

def _ui_back_to_root_kb(text: str = "🧰 В меню") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="menu:root")]]
    )

def _ui_get_state(chat_id: int, user_id: int) -> dict:
    key = (chat_id, user_id)
    cached = _ui_cache.get(key)
    if cached is not None:
        return cached
    with connect() as con, closing(con.cursor()) as c:
        row = c.execute(
            "SELECT menu_message_id, content_message_id FROM ui_state WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        ).fetchone()
    state = {"menu": (row[0] if row else None), "content": (row[1] if row else None)}
    _ui_cache[key] = state
    return state

def _ui_save_state(chat_id: int, user_id: int, *, menu=_UNSET, content=_UNSET) -> None:
    now = datetime.now().isoformat()
    prev = _ui_get_state(chat_id, user_id)
    new_menu = prev.get("menu") if menu is _UNSET else menu
    new_content = prev.get("content") if content is _UNSET else content
    with connect() as con, closing(con.cursor()) as c:
        c.execute(
            """
            INSERT INTO ui_state(chat_id, user_id, menu_message_id, content_message_id, updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
              menu_message_id=excluded.menu_message_id,
              content_message_id=excluded.content_message_id,
              updated_at=excluded.updated_at
            """,
            (chat_id, user_id, new_menu, new_content, now),
        )
        con.commit()
    _ui_cache[(chat_id, user_id)] = {"menu": new_menu, "content": new_content}

async def _ui_ensure_main_menu(bot: Bot, chat_id: int, user_id: int) -> int:
    """
    Гарантирует наличие первого (статичного) сообщения с главным меню.
    Возвращает message_id сообщения меню.
    """
    init_db()
    role = get_role_label(user_id)
    target_chat_id, extra = _ui_route_kwargs(chat_id)
    state = _ui_get_state(target_chat_id, user_id)
    menu_id = state.get("menu")
    desired_text = _ui_main_menu_text(user_id)

    # Lock per (target_chat_id, user_id) so menu/content ops don't race
    async with _ui_get_lock(target_chat_id, user_id):
        # re-read inside lock (state may have changed)
        state = _ui_get_state(target_chat_id, user_id)
        menu_id = state.get("menu")

        # Главное меню теперь "статичное" и несёт ReplyKeyboard с кнопкой Reset.
        # ReplyKeyboard нельзя безопасно обновлять через editMessage*, поэтому:
        # - если menu_message_id есть, считаем, что меню уже есть и НЕ трогаем его
        # - восстановить его всегда можно через /reset или кнопку "🔄 Сброс"
        if menu_id:
            return int(menu_id)

        msg = await bot.send_message(
            target_chat_id,
            desired_text,
            reply_markup=reply_menu_kb(),
            disable_web_page_preview=True,
            **extra,
        )
        _ui_save_state(target_chat_id, user_id, menu=msg.message_id)
        return msg.message_id

async def _ui_clear_content(bot: Bot, chat_id: int, user_id: int) -> None:
    """
    Deletes the content message (2nd UI message) and clears ui_state.content_message_id.
    Used when returning to root so only the main menu remains.
    """
    init_db()
    target_chat_id, _extra = _ui_route_kwargs(chat_id)
    async with _ui_get_lock(target_chat_id, user_id):
        state = _ui_get_state(target_chat_id, user_id)
        content_id = state.get("content")
        if not content_id:
            return
        try:
            await bot.delete_message(target_chat_id, int(content_id))
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        except Exception:
            pass
        _ui_save_state(target_chat_id, user_id, content=None)

async def _ui_edit_content(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> int:
    """
    Редактирует/создаёт второе сообщение (контент/подменю). Всегда целимся только в него.
    Возвращает message_id контент-сообщения.
    """
    init_db()
    target_chat_id, extra = _ui_route_kwargs(chat_id)

    # 1) убедимся, что главное меню есть (чтобы схема "2 сообщения" сохранялась)
    await _ui_ensure_main_menu(bot, chat_id, user_id)

    async with _ui_get_lock(target_chat_id, user_id):
        # re-read inside lock to avoid races (double taps / parallel callback processing)
        state = _ui_get_state(target_chat_id, user_id)
        content_id = state.get("content")
        if content_id:
            try:
                await bot.edit_message_text(
                    chat_id=target_chat_id,
                    message_id=content_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                return int(content_id)
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    # Telegram may report "not modified" even when we want to refresh the keyboard.
                    # Best-effort: try to update reply_markup explicitly.
                    try:
                        await bot.edit_message_reply_markup(
                            chat_id=target_chat_id,
                            message_id=content_id,
                            reply_markup=reply_markup,
                        )
                    except Exception:
                        pass
                    return int(content_id)
                if "message to edit not found" in str(e).lower():
                    content_id = None
                    _ui_save_state(target_chat_id, user_id, content=None)

        # 2) если нет/не редактируется — отправим новый контент ниже меню
        msg = await bot.send_message(
            target_chat_id,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            **extra,
        )

        # попробуем подчистить "старый контент", если он был (чтобы стремиться к 2 сообщениям)
        old_content = state.get("content")
        if old_content and old_content != msg.message_id:
            try:
                await bot.delete_message(target_chat_id, old_content)
            except TelegramBadRequest:
                pass

        _ui_save_state(target_chat_id, user_id, content=msg.message_id)
        return msg.message_id

def _ui_route_kwargs(current_chat_id: int) -> tuple[int, dict]:
    """
    Returns (target_chat_id, extra_kwargs) so UI always goes to the 🤖 topic.
    """
    target_chat_id = current_chat_id
    extra: dict = {}
    if WORK_CHAT_ID and current_chat_id == WORK_CHAT_ID and WORK_TOPIC_ID:
        target_chat_id = WORK_CHAT_ID
        extra["message_thread_id"] = WORK_TOPIC_ID
    return target_chat_id, extra

def _is_regular_user_message(message: Message) -> bool:
    user = message.from_user
    if not user:
        return False
    if user.is_bot:
        return False
    if is_admin(message):
        return False
    return True

def _is_allowed_topic(message: Message) -> bool:
    """Проверяет, разрешена ли тема для команд бота"""
    # В "read-only" чате бот не реагирует на команды/текст вообще
    if READONLY_CHAT_ID and message.chat.id == READONLY_CHAT_ID:
        return False
    # Если это не супергруппа или не настроены темы - разрешаем
    if not GROUP_CHAT_ID or message.chat.id != GROUP_CHAT_ID:
        return True
    
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None:
        return False  # В супергруппе без темы команды не обрабатываем
    
    # Разрешаем только в темах "Часы" и "Отчет"
    return thread_id in (HOURS_THREAD_ID, REPORTS_THREAD_ID)


def robot_banner_keyboard() -> Optional[InlineKeyboardMarkup]:
    if not ROBOT_BANNER_URL:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=ROBOT_BANNER_BUTTON or "Open bot", url=ROBOT_BANNER_URL)]
        ]
    )


async def ensure_robot_banner(bot: Bot, *, force_new: bool = False) -> None:
    global ROBOT_BANNER_MESSAGE_ID
    if ROBOT_CHAT_ID is None or ROBOT_TOPIC_ID is None or not ROBOT_BANNER_TEXT:
        return
    keyboard = robot_banner_keyboard()
    if ROBOT_BANNER_MESSAGE_ID and not force_new:
        try:
            await bot.edit_message_text(
                ROBOT_BANNER_TEXT,
                chat_id=ROBOT_CHAT_ID,
                message_id=ROBOT_BANNER_MESSAGE_ID,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return
        except TelegramBadRequest:
            print("[robot-banner] stored ROBOT_BANNER_MESSAGE_ID is invalid; sending new banner")
    if ROBOT_BANNER_MESSAGE_ID and force_new:
        try:
            await bot.delete_message(ROBOT_CHAT_ID, ROBOT_BANNER_MESSAGE_ID)
        except TelegramBadRequest:
            pass
    msg = await bot.send_message(
        ROBOT_CHAT_ID,
        ROBOT_BANNER_TEXT,
        message_thread_id=ROBOT_TOPIC_ID,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    ROBOT_BANNER_MESSAGE_ID = msg.message_id
    print(f"[robot-banner] update .env with ROBOT_BANNER_MESSAGE_ID={msg.message_id}")


async def _notify_user(bot: Bot, user_id: int, text: str) -> None:
    if not text:
        return
    try:
        await bot.send_message(user_id, text)
    except TelegramForbiddenError:
        pass

async def _edit_or_send(bot: Bot, chat_id: int, user_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup]=None):
    await _ui_edit_content(bot, chat_id, user_id, text, reply_markup=reply_markup)

async def _send_new_message(bot: Bot, chat_id: int, user_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup]=None):
    """
    В новой схеме UI сообщений всегда два (главное меню + контент).
    Поэтому вместо "послать новое и удалить старое" — просто редактируем контент.
    """
    await _ui_edit_content(bot, chat_id, user_id, text, reply_markup=reply_markup)

def reply_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Сброс")]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )

def phone_contact_kb() -> ReplyKeyboardMarkup:
    """
    Кнопка, которая отправляет контакт СВОЕГО номера телефона боту.
    Используем как подтверждение номера (аналог SMS-кода).
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить контакт", request_contact=True)],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

async def _ui_reset(bot: Bot, chat_id: int, user_id: int) -> None:
    """
    "Мягкий reset" UI: очищает ui_state (menu/content), пытается удалить UI-сообщения,
    сбрасывает FSM и создаёт новое главное меню.
    Важно: это НЕ удаляет историю отчётов (БД reports).
    Полностью "очистить весь чат" бот не может, т.к. Telegram API не даёт список сообщений.
    """
    init_db()
    target_chat_id, _extra = _ui_route_kwargs(chat_id)
    async with _ui_get_lock(target_chat_id, user_id):
        st = _ui_get_state(target_chat_id, user_id)
        # удаляем контент и меню (если возможно)
        for key in ("content", "menu"):
            mid = st.get(key)
            if not mid:
                continue
            try:
                await bot.delete_message(target_chat_id, int(mid))
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
            except Exception:
                pass
        _ui_save_state(target_chat_id, user_id, menu=None, content=None)
    # 1) создаём статичное меню (reply keyboard with "🔄 Сброс")
    await _ui_ensure_main_menu(bot, chat_id, user_id)
    # 2) и сразу рисуем контент-меню с inline кнопками (чтобы не требовался /start)
    role = get_role_label(user_id)
    await _ui_edit_content(bot, chat_id, user_id, "Выберите действие:", reply_markup=main_menu_kb(role))

# Удаляем отдельные клавиатуры - используем только одну для всех

# -------------- Публикации в топике статистики --------------
async def _stats_target():
    # Определяем куда публиковать: приоритет STATS_*, иначе WORK_*, иначе None
    chat_id = STATS_CHAT_ID or WORK_CHAT_ID
    thread_id = STATS_TOPIC_ID or WORK_TOPIC_ID
    return chat_id, thread_id

def _format_user(who: dict) -> str:
    full = (who.get("full_name") or "").strip()
    uname = (who.get("username") or "").strip()
    if full:
        return full
    if uname:
        return "@" + uname
    return str(who.get("user_id"))

def _format_report_line(r: dict) -> str:
    def esc(v: object) -> str:
        return html.escape("" if v is None else str(v))

    who = _format_user({"full_name": r.get("reg_name"), "username": r.get("username"), "user_id": r.get("user_id")})
    who = esc(who)
    work_date = esc(r.get("work_date") or "—")
    location = esc(r.get("location") or "—")
    activity = esc(r.get("activity") or "—")
    hours = esc(r.get("hours") if r.get("hours") is not None else "—")

    extra: List[str] = []
    mtype = (r.get("machine_type") or "").strip()
    mname = (r.get("machine_name") or "").strip()
    if mtype or mname:
        extra.append(f"🚜 {esc((mtype + ' ' + mname).strip())}")
    crop = (r.get("crop") or "").strip()
    if crop:
        extra.append(f"🌱 {esc(crop)}")
    trips = r.get("trips")
    if trips is not None:
        try:
            trips_int = int(trips)
        except Exception:
            trips_int = None
        if trips_int is not None and trips_int != 0:
            extra.append(f"🚚 рейсы: {esc(trips_int)}")

    return (
        f"👤 <b>{who}</b>\n"
        f"📅 {work_date}\n"
        f"📍 {location}\n"
        f"🧰 {activity}\n"
        + (("\n".join(extra) + "\n") if extra else "")
        + f"⏱️ {hours} ч\n"
        f"ID: <code>#{esc(r.get('id'))}</code>"
    )

def _format_report_changes(before: Optional[dict], after: dict) -> str:
    """
    Возвращает список изменений (что -> на что) для публикации в общем чате.
    """
    if not before:
        return ""

    def esc(v: object) -> str:
        return html.escape("" if v is None else str(v))

    def norm_str(v: object) -> str:
        return "" if v is None else str(v).strip()

    def machine_str(r: dict) -> str:
        mt = norm_str(r.get("machine_type"))
        mn = norm_str(r.get("machine_name"))
        return (mt + (" " + mn if mn else "")).strip()

    pairs: List[Tuple[str, str, str, str]] = []

    # label, before_value, after_value, icon
    pairs.append(("Дата", norm_str(before.get("work_date")), norm_str(after.get("work_date")), "📅"))
    pairs.append(("Часы", norm_str(before.get("hours")), norm_str(after.get("hours")), "⏱️"))
    pairs.append(("Место", norm_str(before.get("location")), norm_str(after.get("location")), "📍"))
    pairs.append(("Работа", norm_str(before.get("activity")), norm_str(after.get("activity")), "🧰"))
    pairs.append(("Техника", machine_str(before), machine_str(after), "🚜"))
    pairs.append(("Культура", norm_str(before.get("crop")), norm_str(after.get("crop")), "🌱"))
    pairs.append(("Рейсы", norm_str(before.get("trips")), norm_str(after.get("trips")), "🚚"))

    changes: List[str] = []
    for label, b, a, icon in pairs:
        b2 = b if b else "—"
        a2 = a if a else "—"
        if b2 != a2:
            changes.append(f"- {icon} <b>{esc(label)}</b>: {esc(b2)} → {esc(a2)}")

    if not changes:
        return ""
    return "🔁 <b>Что изменили</b>:\n" + "\n".join(changes)

async def stats_notify_created(bot: Bot, report_id:int):
    r = get_report(report_id)
    if not r:
        return
    if int(r.get("user_id") or 0) in HIDE_IDS:
        return
    chat_id, thread_id = await _stats_target()
    if not chat_id:
        return  # не настроено — тихо выходим
    text = "✅ Новая запись\n\n" + _format_report_line(r)
    if chat_id and thread_id:
        m = await bot.send_message(chat_id, text, message_thread_id=thread_id)
    else:
        m = await bot.send_message(chat_id, text)
    stat_save_msg(report_id, chat_id, thread_id or 0, m.message_id, "created")

async def stats_notify_changed(bot: Bot, report_id:int, before: Optional[dict] = None):
    r = get_report(report_id)
    if not r:
        return
    if int(r.get("user_id") or 0) in HIDE_IDS:
        return
    prev = stat_get_msg(report_id)
    chat_id, thread_id = await _stats_target()
    if not chat_id:
        return

    diff = _format_report_changes(before, r)
    announce_text = (
        "✏️ Изменена запись\n\n" + (diff + "\n\n" if diff else "") + _format_report_line(r)
    )
    current_text = "🧾 Текущая запись\n\n" + _format_report_line(r)

    # 1) Пытаемся обновить "закреплённое" сообщение отчёта (чтобы оно всегда было актуальным)
    if prev:
        p_chat, _, p_msg, _ = prev
        try:
            await bot.edit_message_text(chat_id=p_chat, message_id=p_msg, text=current_text)
            stat_save_msg(report_id, p_chat, thread_id or 0, p_msg, "current")
            # 2) И отдельным сообщением объявляем, что именно поменяли (чтобы это было заметно в чате)
            if thread_id:
                await bot.send_message(chat_id, announce_text, message_thread_id=thread_id)
            else:
                await bot.send_message(chat_id, announce_text)
            return
        except TelegramBadRequest:
            prev = None

    # Если не было предыдущего поста (или не смогли отредактировать) — публикуем "изменение" как новый пост
    if thread_id:
        m = await bot.send_message(chat_id, announce_text, message_thread_id=thread_id)
    else:
        m = await bot.send_message(chat_id, announce_text)
    stat_save_msg(report_id, chat_id, thread_id or 0, m.message_id, "changed")

async def stats_notify_deleted(bot: Bot, report_id:int, deleted: Optional[dict] = None):
    prev = stat_get_msg(report_id)
    deleted_text = ""
    if deleted:
        try:
            deleted_text = _format_report_line(deleted)
        except Exception:
            deleted_text = ""
    # Если это скрытый пользователь — не публикуем удаление в общий чат
    try:
        if deleted and int(deleted.get("user_id") or 0) in HIDE_IDS:
            return
    except Exception:
        pass

    delete_text = ("🗑 Удалена запись\n\n" + deleted_text) if deleted_text else f"🗑 Удалена запись\n\nID: <code>#{html.escape(str(report_id))}</code>"

    # нет предыдущего поста — отправим отдельным сообщением
    chat_id, thread_id = await _stats_target()
    if not chat_id:
        return

    # 1) Обновляем "закреплённое" сообщение отчёта (если было), чтобы было видно что запись удалена
    if prev:
        p_chat, _, p_msg, _ = prev
        try:
            await bot.edit_message_text(chat_id=p_chat, message_id=p_msg, text=delete_text)
            stat_save_msg(report_id, p_chat, (prev[1] or 0), p_msg, "deleted")
            # 2) И отдельным сообщением объявляем удаление (чтобы это было заметно в чате)
            if thread_id:
                await bot.send_message(chat_id, delete_text, message_thread_id=thread_id)
            else:
                await bot.send_message(chat_id, delete_text)
            return
        except TelegramBadRequest:
            prev = None

    # Если не было предыдущего поста (или не смогли отредактировать) — просто публикуем
    if thread_id:
        m = await bot.send_message(chat_id, delete_text, message_thread_id=thread_id)
    else:
        m = await bot.send_message(chat_id, delete_text)
    stat_save_msg(report_id, chat_id, thread_id or 0, m.message_id, "deleted")

def days_keyboard() -> InlineKeyboardMarkup:
    # сегодня, -4 дня назад (всего 5 кнопок), вертикально
    today = date.today()
    items: List[date] = [today]
    
    # Прошлые дни: -1, -2, -3, -4
    for i in range(1, 5):
        past_date = today - timedelta(days=i)
        items.append(past_date)
    
    def fmt(d: date) -> str:
        if d == today:
            return "Сегодня"
        elif d == today - timedelta(days=1):
            return "Вчера"
        elif d == today - timedelta(days=2):
            return "Позавчера"
        else:
            return d.strftime("%d.%m.%y")
    
    kb = InlineKeyboardBuilder()
    for d in items:
        kb.row(InlineKeyboardButton(text=fmt(d), callback_data=f"work:date:{d.isoformat()}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="work:back:loc"))
    return kb.as_markup()

def hours_keyboard() -> InlineKeyboardMarkup:
    # 1..24 сеткой 6x4
    kb = InlineKeyboardBuilder()
    for h in range(1, 25):
        kb.button(text=str(h), callback_data=f"work:hours:{h}")
    kb.adjust(6)  # 6 столбцов
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="work:back:date"))
    return kb.as_markup()

def main_menu_kb(role: str) -> InlineKeyboardMarkup:
    """
    Строит меню в зависимости от роли.
    role: admin | tim | it | brigadier | user
    """
    kb = InlineKeyboardBuilder()
    if role == "tim":
        kb.button(text="ОТД", callback_data="otd:start")
        kb.button(text="📊 Статистика", callback_data="menu:stats")
        kb.button(text="⚙️ Настройки", callback_data="menu:name")
        kb.adjust(2, 1)
        return kb.as_markup()

    if role == "it":
        kb.button(text="☄️ ОТД", callback_data="otd:start")
        kb.button(text="📊 Статистика", callback_data="menu:stats")
        kb.button(text="⚙️ Настройки", callback_data="menu:name")
        kb.adjust(2, 1)
        return kb.as_markup()

    if role == "brigadier":
        kb.button(text="ОБ", callback_data="brig:report")
        kb.button(text="ОТД", callback_data="otd:start")
        # Унифицированная статистика (один вход для всех ролей)
        kb.button(text="Статистика", callback_data="menu:stats")
        kb.button(text="Настройки", callback_data="menu:name")
        kb.adjust(2, 2)
        return kb.as_markup()

    if role == "admin":
        kb.button(text="ОТД", callback_data="otd:start")
        kb.button(text="📊 Статистика", callback_data="menu:stats")
        kb.button(text="⚙️ Настройки", callback_data="menu:name")
        kb.button(text="⚙️ Админ", callback_data="menu:admin")
        kb.adjust(2, 2)
        return kb.as_markup()

    # обычный пользователь
    kb.button(text="ОТД", callback_data="otd:start")
    kb.button(text="Статистика", callback_data="menu:stats")
    kb.button(text="Настройки", callback_data="menu:name")
    kb.adjust(2, 1)
    return kb.as_markup()

def settings_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Сменить ФИО", callback_data="menu:name:change")
    kb.button(text="📱 Номер телефона", callback_data="menu:phone")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(1)
    return kb.as_markup()

def work_groups_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Техника", callback_data="work:grp:tech")
    kb.button(text="Ручная", callback_data="work:grp:hand")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(2, 1)
    return kb.as_markup()

def work_groups_kb_user() -> InlineKeyboardMarkup:
    """Клавиатура для обычных пользователей без кнопки Назад в админ меню"""
    kb = InlineKeyboardBuilder()
    kb.button(text="Техника", callback_data="work:grp:tech")
    kb.button(text="Ручная", callback_data="work:grp:hand")
    kb.button(text="🔙 Назад", callback_data="menu:start")
    kb.adjust(2, 1)
    return kb.as_markup()

def user_full_menu_kb() -> InlineKeyboardMarkup:
    """Полное меню для обычных пользователей (без админ функций)"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚜 Работа", callback_data="menu:work")
    kb.button(text="📊 Статистика", callback_data="menu:stats")
    kb.button(text="📝 Перепись", callback_data="menu:edit")
    kb.button(text="✏️ Изменить имя", callback_data="menu:name")
    kb.adjust(2, 2)
    return kb.as_markup()

def activities_kb(kind: str) -> InlineKeyboardMarkup:
    names = list_activities(GROUP_TECH if kind=="tech" else GROUP_HAND)
    kb = InlineKeyboardBuilder()
    for n in names:
        kb.button(text=n, callback_data=f"work:act:{kind}:{n}")
    kb.button(text="Прочее…", callback_data=f"work:act:{kind}:__other__")
    kb.button(text="🔙 Назад", callback_data="work:back:grp")
    kb.adjust(2)
    return kb.as_markup()

def loc_groups_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Поля", callback_data="work:locgrp:fields")
    kb.button(text="Склад", callback_data="work:locgrp:ware")
    kb.button(text="🔙 Назад", callback_data="work:back:act")
    kb.adjust(2,1)
    return kb.as_markup()

# -------- OTD helper keyboards --------
def otd_days_keyboard() -> InlineKeyboardMarkup:
    today = date.today()
    items: List[date] = [today]
    for i in range(1, 5):
        items.append(today - timedelta(days=i))
    kb = InlineKeyboardBuilder()
    for d in items:
        if d == today:
            label = "Сегодня"
        elif d == today - timedelta(days=1):
            label = "Вчера"
        else:
            label = d.strftime("%d.%m.%y")
        kb.row(InlineKeyboardButton(text=label, callback_data=f"otd:date:{d.isoformat()}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    return kb.as_markup()

def otd_hours_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for h in range(1, 25):
        kb.button(text=str(h), callback_data=f"otd:hours:{h}")
    kb.adjust(6)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:date"))
    return kb.as_markup()

def otd_type_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Техника", callback_data="otd:type:tech")
    kb.button(text="Ручная", callback_data="otd:type:hand")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:hours"))
    return kb.as_markup()

def otd_machine_type_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kinds = list_machine_kinds(limit=50, offset=0)
    for k in kinds:
        kb.button(text=(k.get("title") or "—")[:64], callback_data=f"otd:mkind:{k['id']}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:type"))
    return kb.as_markup()

def otd_machine_name_kb(kind_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = list_machine_items(kind_id, limit=50, offset=0)
    for it in items:
        kb.button(text=(it.get("name") or "—")[:64], callback_data=f"otd:mname:{it['id']}")
    kb.button(text="Прочее", callback_data=f"otd:mname:__other__:{kind_id}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:mkind"))
    return kb.as_markup()

def otd_tractor_work_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for w in OTD_TRACTOR_WORKS:
        kb.button(text=w, callback_data=f"otd:twork:{w}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:tractor"))
    return kb.as_markup()

def otd_fields_kb(back_to:str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f_name in OTD_FIELDS:
        kb.button(text=f_name, callback_data=f"{back_to}:{f_name}")
    # отдельной опцией
    kb.button(text="Склад", callback_data=f"{back_to}:Склад")
    # свободный ввод
    kb.button(text="Прочее", callback_data=f"{back_to}:__other__")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:fieldprev"))
    return kb.as_markup()

def otd_crops_kb(*, kamaz: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    crops = KAMAZ_CARGO_LIST if kamaz else OTD_CROPS
    for c_name in crops:
        # "Прочее" должно вести на свободный ввод (а не сохраняться как значение)
        if (c_name or "").strip() == "Прочее":
            kb.button(text="Прочее…", callback_data="otd:crop:__other__")
        else:
            kb.button(text=c_name, callback_data=f"otd:crop:{c_name}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:loc_or_work"))
    return kb.as_markup()

def otd_hand_work_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for w in OTD_HAND_WORKS:
        kb.button(text=w, callback_data=f"otd:hand:{w}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:type"))
    return kb.as_markup()

def otd_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="otd:confirm:ok")
    kb.button(text="✏️ Изменить", callback_data="otd:confirm:edit")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    return kb.as_markup()

def otd_confirm_edit_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Дата", callback_data="otd:edit:date")
    kb.button(text="Часы", callback_data="otd:edit:hours")
    kb.button(text="Тип работы", callback_data="otd:edit:type")
    kb.adjust(2,1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к подтверждению", callback_data="otd:confirm:back"))
    return kb.as_markup()

def locations_kb(kind: str) -> InlineKeyboardMarkup:
    names = list_locations(GROUP_FIELDS if kind == "fields" else GROUP_WARE)
    kb = InlineKeyboardBuilder()
    for n in names:
        kb.button(text=n, callback_data=f"work:loc:{kind}:{n}")
    if kind == "fields":
        # отдельной опцией
        kb.button(text="Склад", callback_data="work:loc:ware:Склад")
        # свободный ввод
        kb.button(text="Прочее", callback_data="work:loc:fields:__other__")
    kb.button(text="🔙 Назад", callback_data="work:back:locgrp")
    kb.adjust(2)
    return kb.as_markup()

def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Роли", callback_data="adm:roles")
    kb.button(text="🗂 Root", callback_data="adm:root")
    kb.button(text="📤 Экспорт отчетов", callback_data="adm:export")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(2,1,1)
    return kb.as_markup()

def admin_root_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Локация", callback_data="adm:root:loc")
    kb.button(text="Работа", callback_data="adm:root:act")
    kb.button(text="Техника", callback_data="adm:root:tech")
    kb.button(text="Культура", callback_data="adm:root:crop")
    kb.button(text="🔙 Назад", callback_data="menu:admin")
    kb.adjust(2,2,1)
    return kb.as_markup()

def admin_root_loc_kb() -> InlineKeyboardMarkup:
    # legacy (оставлено для совместимости)
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ К списку", callback_data="adm:root:loc")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(1,1)
    return kb.as_markup()

def admin_root_act_kb() -> InlineKeyboardMarkup:
    # legacy (оставлено для совместимости)
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ К выбору типа", callback_data="adm:root:act")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(1,1)
    return kb.as_markup()

def admin_root_loc_list_kb(page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    total = count_locations()
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    items = list_locations_rows(limit=page_size, offset=offset)

    kb = InlineKeyboardBuilder()
    # В начале списка — кнопка добавления
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data="adm:root:loc:add"))
    for it in items:
        grp = it.get("grp") or ""
        grp_lbl = "поля" if grp == GROUP_FIELDS else ("склад" if grp == GROUP_WARE else grp)
        kb.button(text=f"{it['name']} ({grp_lbl})"[:64], callback_data=f"adm:root:loc:item:{it['id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:root:loc:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="adm:root:loc")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:root:loc:page:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root"))
    return kb.as_markup()

def admin_root_loc_item_kb(loc_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data=f"adm:root:loc:edit:{loc_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:root:loc:del:{loc_id}")
    kb.button(text="🔙 Назад", callback_data="adm:root:loc")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(2,2)
    return kb.as_markup()

def admin_root_loc_add_grp_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Поля", callback_data="adm:root:loc:addgrp:fields")
    kb.button(text="Склад", callback_data="adm:root:loc:addgrp:ware")
    kb.button(text="🔙 Назад", callback_data="adm:root:loc")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_root_act_pick_grp_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Техника", callback_data="adm:root:act:grp:tech")
    kb.button(text="Ручная", callback_data="adm:root:act:grp:hand")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_root_act_list_kb(grp: str, page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    grp_name = GROUP_TECH if grp == "tech" else GROUP_HAND
    total = count_activities(grp_name)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    items = list_activities_rows(grp=grp_name, limit=page_size, offset=offset)

    kb = InlineKeyboardBuilder()
    # В начале списка — кнопка добавления
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data=f"adm:root:act:add:{grp}"))
    for it in items:
        kb.button(text=it["name"][:64], callback_data=f"adm:root:act:item:{grp}:{it['id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:root:act:page:{grp}:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data=f"adm:root:act:grp:{grp}")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:root:act:page:{grp}:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:act"))
    kb.row(InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root"))
    return kb.as_markup()

def admin_root_act_item_kb(grp: str, act_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data=f"adm:root:act:edit:{grp}:{act_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:root:act:del:{grp}:{act_id}")
    kb.button(text="🔙 Назад", callback_data=f"adm:root:act:grp:{grp}")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(2,2)
    return kb.as_markup()

def admin_root_tech_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Трактор", callback_data="adm:root:tech:tractor")
    kb.button(text="КамАЗ", callback_data="adm:root:tech:kamaz")
    kb.button(text="➕ Добавить тип", callback_data="adm:root:techkind:add")
    kb.button(text="🗑 Удалить тип", callback_data="adm:root:techkind:del")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,2,1)
    return kb.as_markup()

def admin_root_tech_actions_kb(sub: str) -> InlineKeyboardMarkup:
    # legacy (оставлено для совместимости)
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ К технике", callback_data="adm:root:tech")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(1,1)
    return kb.as_markup()

def admin_root_tech_items_kb(kind_id: int, page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    mk = get_machine_kind(kind_id) or {"title": "—"}
    total = count_machine_items(kind_id)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    items = list_machine_items(kind_id, limit=page_size, offset=offset)

    kb = InlineKeyboardBuilder()
    # В начале списка — кнопка добавления
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data=f"adm:root:tech:add:{kind_id}"))
    for it in items:
        kb.button(text=(it.get("name") or "—")[:64], callback_data=f"adm:root:tech:item:{kind_id}:{it['id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:root:tech:page:{kind_id}:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data=f"adm:root:tech:tractor")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:root:tech:page:{kind_id}:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:tech"))
    kb.row(InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root"))
    return kb.as_markup()

def admin_root_tech_item_kb(kind_id: int, item_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data=f"adm:root:tech:edit:{kind_id}:{item_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:root:tech:del:{kind_id}:{item_id}")
    kb.button(text="🔙 Назад", callback_data=f"adm:root:tech:tractor")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(2,2)
    return kb.as_markup()

def admin_root_tech_kamaz_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить КамАЗ", callback_data="adm:root:techkind:delpick:2")
    kb.button(text="🔙 Назад", callback_data="adm:root:tech")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(1,1,1)
    return kb.as_markup()

def admin_root_tech_kind_del_kb(page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    total = count_machine_kinds()
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    kinds = list_machine_kinds(limit=page_size, offset=offset)

    kb = InlineKeyboardBuilder()
    for k in kinds:
        kb.button(text=f"🗑 {k['title']}"[:64], callback_data=f"adm:root:techkind:delpick:{k['id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:root:techkind:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="adm:root:techkind:del")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:root:techkind:page:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:tech"))
    kb.row(InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root"))
    return kb.as_markup()

def admin_root_crop_kb() -> InlineKeyboardMarkup:
    # legacy (оставлено для совместимости)
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ К списку", callback_data="adm:root:crop")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(1,1)
    return kb.as_markup()

def admin_root_crop_list_kb(page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    total = count_crops()
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    items = list_crops_rows(page_size, offset)

    kb = InlineKeyboardBuilder()
    # В начале списка — кнопка добавления
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data="adm:root:crop:add"))
    for it in items:
        kb.button(text=it["name"][:64], callback_data=f"adm:root:crop:item:{it['id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:root:crop:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="adm:root:crop")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:root:crop:page:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root"))
    return kb.as_markup()

def admin_root_crop_item_kb(crop_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data=f"adm:root:crop:edit:{crop_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:root:crop:delid:{crop_id}")
    kb.button(text="🔙 Назад", callback_data="adm:root:crop")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(2,2)
    return kb.as_markup()

def admin_roles_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Выдать бригадира", callback_data="adm:role:add:brig")
    kb.button(text="➖ Снять бригадира", callback_data="adm:role:del:brig")
    kb.button(text="🔙 Назад", callback_data="menu:admin")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_role_add_brig_kb(page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    total = count_registered_users()
    kb = InlineKeyboardBuilder()
    if total <= 0:
        kb.button(text="— нет зарегистрированных —", callback_data="adm:roles")
        kb.button(text="🔙 Назад", callback_data="adm:roles")
        kb.adjust(1,1)
        return kb.as_markup()

    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    users = list_registered_users(page_size, offset)

    for u in users:
        label = _display_user(u.get("full_name"), u.get("username"), u["user_id"])
        kb.button(text=label[:64], callback_data=f"adm:role:add:brig:pick:{u['user_id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:role:add:brig:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="adm:roles")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:role:add:brig:page:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles"))
    return kb.as_markup()

def admin_role_del_brig_kb(page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    total = count_brigadiers_known()
    kb = InlineKeyboardBuilder()
    if total <= 0:
        kb.button(text="— бригадиров нет —", callback_data="adm:roles")
        kb.button(text="🔙 Назад", callback_data="adm:roles")
        kb.adjust(1,1)
        return kb.as_markup()

    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    offset = page * page_size
    brig = list_brigadiers_known(page_size, offset)

    for b in brig:
        label = _display_user(b.get("full_name"), b.get("username"), b["user_id"])
        kb.button(text=label[:64], callback_data=f"adm:role:del:brig:pick:{b['user_id']}")
    kb.adjust(1)

    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:role:del:brig:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="adm:roles")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:role:del:brig:page:{page+1}")
        nav.adjust(3)
        kb.attach(nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles"))
    return kb.as_markup()

def admin_pick_group_kb(kind:str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if kind == "act":
        kb.button(text="Техника", callback_data="adm:grp:act:tech")
        kb.button(text="Ручная", callback_data="adm:grp:act:hand")
    else:
        kb.button(text="Поля", callback_data="adm:grp:loc:fields")
        kb.button(text="Склад", callback_data="adm:grp:loc:ware")
    kb.button(text="🔙 Назад", callback_data="menu:admin")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_delete_list_kb(kind:str, grp:str) -> InlineKeyboardMarkup:
    # kind: "act" | "loc"; grp: tech/hand for act, fields/ware for loc
    if kind == "act":
        group_name = GROUP_TECH if grp == "tech" else GROUP_HAND
        items = list_activities(group_name)
    else:
        group_name = GROUP_FIELDS if grp == "fields" else GROUP_WARE
        items = list_locations(group_name)

    kb = InlineKeyboardBuilder()
    for it in items:
        # Создаём безопасный callback_data, ограничивая длину и убирая спецсимволы
        safe_name = it.replace(":", "_").replace(" ", "_")[:20]
        callback_data = f"adm:delpick:{kind}:{grp}:{safe_name}"
        kb.button(text=f"🗑 {it}", callback_data=callback_data)

    # Если список пуст, покажем заглушку
    if not items:
        kb.button(text="— список пуст —", callback_data="adm:grp:noop")

    kb.button(text="🔙 Назад", callback_data=f"adm:grp:{kind}")
    kb.adjust(2)
    return kb.as_markup()

# -----------------------------
# Модерация тем
# -----------------------------

async def is_admin_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False

# -----------------------------
# Бот (v3 Router)
# -----------------------------

router = Router()
router_topics = Router()  # Отдельный роутер для модерации тем

# В read-only чате запрещаем обработку ЛЮБЫХ входящих апдейтов обычным роутером:
# никаких команд, меню, кнопок и т.п. (в группе должны быть только отчёты).
if READONLY_CHAT_ID is not None:
    # Используем MagicFilter (F.*), а не lambda: в aiogram v3 lambda может не применяться как фильтр.
    router.message.filter(F.chat.id != READONLY_CHAT_ID)
    # CallbackQuery обычно всегда имеет message, но на всякий случай пропускаем те, где message отсутствует.
    router.callback_query.filter(F.message.is_(None) | (F.message.chat.id != READONLY_CHAT_ID))

# Полный read-only чат: удаляем сообщения обычных пользователей (включая команды).
if READONLY_CHAT_ID is not None:
    # И дополнительно глушим callback-и (нажатия на inline-кнопки), чтобы не было "реакций" в чате.
    @router_topics.callback_query(F.message.chat.id == READONLY_CHAT_ID)
    async def guard_readonly_callbacks(c: CallbackQuery):
        try:
            await c.answer()
        except Exception:
            pass

    @router_topics.message(
        F.chat.id == READONLY_CHAT_ID,
    )
    async def guard_readonly_chat(message: Message):
        user = message.from_user
        if not user:
            return
        # Разрешаем бота и админов
        bot_me = await message.bot.me()
        if user.id == bot_me.id or await is_admin_user(message.bot, message.chat.id, user.id):
            return
        # Все остальные удаляем молча
        try:
            await message.bot.delete_message(message.chat.id, message.message_id)
        except TelegramForbiddenError as e:
            # Обычно это значит, что бот не админ / нет права "Delete messages"
            logging.warning(f"[readonly] cannot delete message in chat {message.chat.id}: {e}")
        except TelegramBadRequest as e:
            logging.info(f"[readonly] delete_message bad request in chat {message.chat.id}: {e}")
        except Exception as e:
            logging.warning(f"[readonly] delete_message failed in chat {message.chat.id}: {e}")

# Модерация темы "Часы" - удаляем все сообщения обычных пользователей
if GROUP_CHAT_ID and HOURS_THREAD_ID:
    @router_topics.message(
        F.chat.type == "supergroup",
        F.chat.id == GROUP_CHAT_ID,
        F.message_thread_id == HOURS_THREAD_ID
    )
    async def guard_hours(message: Message):
        # Разрешаем бота и админов
        bot_me = await message.bot.me()
        if message.from_user and (
            message.from_user.id == bot_me.id or
            await is_admin_user(message.bot, message.chat.id, message.from_user.id)
        ):
            return
        # Все остальные удаляем
        try:
            await message.bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass

# Модерация темы "Отчёт" - удаляем все сообщения обычных пользователей
if GROUP_CHAT_ID and REPORTS_THREAD_ID:
    @router_topics.message(
        F.chat.type == "supergroup",
        F.chat.id == GROUP_CHAT_ID,
        F.message_thread_id == REPORTS_THREAD_ID
    )
    async def guard_reports(message: Message):
        # Разрешаем бота и админов
        bot_me = await message.bot.me()
        if message.from_user and (
            message.from_user.id == bot_me.id or
            await is_admin_user(message.bot, message.chat.id, message.from_user.id)
        ):
            return
        # Все остальные удаляем
        try:
            await message.bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass

# Команда инициализации темы "Часы"
@router_topics.message(Command("init_hours"))
async def init_hours(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    # Только админам
    if not await is_admin_user(message.bot, message.chat.id, message.from_user.id):
        return
    
    if not GROUP_CHAT_ID or not HOURS_THREAD_ID or not BOT_USERNAME:
        await message.answer("❌ Не настроены переменные GROUP_CHAT_ID, HOURS_THREAD_ID или BOT_USERNAME в .env")
        return
    
    # Отправляем сообщение с кнопкой для перехода в ЛС бота
    text = "⏰ <b>Часы</b> ⏰"
    
    # Создаем кнопку-переходник на бота
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="BOT",
            url=f"https://t.me/{BOT_USERNAME}"
        )]
    ])
    
    try:
        msg = await message.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            message_thread_id=HOURS_THREAD_ID,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        # Закрепляем сообщение
        try:
            await message.bot.pin_chat_message(
                chat_id=GROUP_CHAT_ID,
                message_id=msg.message_id,
                disable_notification=True
            )
        except Exception:
            pass
    except Exception:
        pass

if ROBOT_CHAT_ID is not None and ROBOT_TOPIC_ID is not None:
    # Охраняем топик робота только для НЕ-команд (текст без '/'),
    # чтобы команды типа /where работали в этом топике
    @router.message(
        F.chat.id == ROBOT_CHAT_ID,
        F.message_thread_id == ROBOT_TOPIC_ID,
        F.text & ~F.text.startswith("/") & (F.text != "🧰 Меню")
    )
    async def guard_robot_topic(message: Message):
        if not _is_regular_user_message(message):
            return
    
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await ensure_robot_banner(message.bot)
        await _notify_user(message.bot, message.from_user.id, ROBOT_NOTIFY_TEXT)



if STATS_CHAT_ID is not None and STATS_TOPIC_ID is not None:
    # Аналогично — пропускаем команды в топике статистики
    @router.message(
        F.chat.id == STATS_CHAT_ID,
        F.message_thread_id == STATS_TOPIC_ID,
        F.text & ~F.text.startswith("/") & (F.text != "🧰 Меню")
    )
    async def guard_stats_topic(message: Message):
        if not _is_regular_user_message(message):
            return
    
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await _notify_user(message.bot, message.from_user.id, STATS_NOTIFY_TEXT)



@router.message(Command("refresh_robot_banner"))
async def cmd_refresh_robot_banner(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        return
    await ensure_robot_banner(message.bot, force_new=True)
    await message.answer("Robot banner refreshed.")

# --- profile requirements (ФИО + телефон) ---
async def _prompt_phone_registration(message_or_cb, state: FSMContext, *, back_cb: str = "menu:root") -> None:
    """
    Просим пользователя указать телефон.
    Важно: подтверждение номера делаем через "request_contact", поэтому корректно работает в личке.
    """
    # Определяем chat_id и bot
    if isinstance(message_or_cb, CallbackQuery):
        bot = message_or_cb.bot
        chat = message_or_cb.message.chat
        chat_id = message_or_cb.message.chat.id
        user_id = message_or_cb.from_user.id
    else:
        bot = message_or_cb.bot
        chat = message_or_cb.chat
        chat_id = message_or_cb.chat.id
        user_id = message_or_cb.from_user.id

    # Лучше делать регистрацию телефона в личке (и подтверждение контактом тоже)
    if getattr(chat, "type", None) != "private":
        await _edit_or_send(
            bot,
            chat_id,
            user_id,
            "📱 Для регистрации телефона откройте бота <b>в личных сообщениях</b> и нажмите /start.\n\n"
            "Там я попрошу номер и попрошу подтвердить его кнопкой «Отправить контакт».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]
            ]),
        )
        return

    await state.set_state(PhoneFSM.waiting_phone_text)
    await _edit_or_send(
        bot,
        chat_id,
        user_id,
        "📱 Введите номер телефона (можно в любом формате: <b>+7</b>, <b>8</b> или просто <b>9XXXXXXXXX</b>).\n"
        "После этого я попрошу подтвердить номер кнопкой «Отправить контакт».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]
        ]),
    )

async def _require_profile(message_or_cb, state: FSMContext, *, back_cb: str = "menu:root") -> Optional[dict]:
    """
    Гарантирует, что пользователь:
      1) указал ФИО
      2) указал телефон (для Google Sheets UserID)
    Если чего-то нет — переводим в соответствующее состояние и возвращаем None.
    """
    u = get_user(message_or_cb.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(
            message_or_cb.bot,
            message_or_cb.message.chat.id if isinstance(message_or_cb, CallbackQuery) else message_or_cb.chat.id,
            message_or_cb.from_user.id,
            "Введите <b>Фамилию Имя</b> для регистрации.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]
            ]),
        )
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.answer()
        return None
    if not _has_phone(u):
        await _prompt_phone_registration(message_or_cb, state, back_cb=back_cb)
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.answer()
        return None
    return u

# -------------- Команды --------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    try:
        logging.info(
            "[start] chat_id=%s type=%s thread_id=%s user_id=%s username=%s",
            getattr(message.chat, "id", None),
            getattr(message.chat, "type", None),
            getattr(message, "message_thread_id", None),
            getattr(message.from_user, "id", None),
            getattr(message.from_user, "username", None),
        )
    except Exception:
        pass
    # Проверяем разрешенную тему для команд.
    # Важно: после /purge_release у пользователей нет профиля, и им нужно иметь возможность
    # запустить регистрацию даже если сообщение пришло из "не той" темы.
    if not _is_allowed_topic(message):
        u0 = get_user(message.from_user.id) if message.from_user else None
        try:
            logging.info(
                "[start] not_allowed_topic=True registered=%s",
                bool(u0 and (u0.get("full_name") or "").strip() and _has_phone(u0)),
            )
        except Exception:
            pass
        if u0 and (u0.get("full_name") or "").strip() and _has_phone(u0):
            return
    init_db()
    u = get_user(message.from_user.id)
    if not u:
        upsert_user(message.from_user.id, None, TZ, message.from_user.username or "")
        u = get_user(message.from_user.id)
    
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "👋 Для начала введите <b>Фамилию Имя</b> (например: <b>Иванов Иван</b>).",
        )
        return

    # Телефон нужен для Google Sheets UserID (совместимость с WhatsApp)
    if not _has_phone(u):
        await _prompt_phone_registration(message, state, back_cb="menu:root")
        return

    await show_main_menu(message.chat.id, message.from_user.id, u, "Готово. Выберите пункт меню.")

@router.message(F.text)
async def auto_register_on_any_text(message: Message, state: FSMContext):
    """
    UX: новый пользователь может начать регистрацию "первым любым сообщением", а не только /start.
    Не вмешиваемся в активные FSM-сценарии и не реагируем в READONLY чате.
    """
    if not message.from_user or message.from_user.is_bot:
        return
    # не мешаем активным сценариям
    if await state.get_state():
        return
    # в read-only чате не реагируем
    if READONLY_CHAT_ID is not None and message.chat.id == READONLY_CHAT_ID:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    try:
        logging.info(
            "[auto-reg] chat_id=%s type=%s thread_id=%s user_id=%s username=%s text=%s",
            getattr(message.chat, "id", None),
            getattr(message.chat, "type", None),
            getattr(message, "message_thread_id", None),
            getattr(message.from_user, "id", None),
            getattr(message.from_user, "username", None),
            (text[:80] + "…") if len(text) > 80 else text,
        )
    except Exception:
        pass
    # если пользователь уже зарегистрирован — ничего не делаем
    u = get_user(message.from_user.id) or {}
    if (u.get("full_name") or "").strip() and _has_phone(u):
        return

    init_db()
    # создадим/обновим пользователя, чтобы был username
    if not u:
        upsert_user(message.from_user.id, None, TZ, message.from_user.username or "")
        u = get_user(message.from_user.id) or {}

    # стараемся удалить "первое сообщение", чтобы не засорять чат
    await _ui_try_delete_user_message(message)

    # запускаем регистрацию по тем же правилам, что и /start
    if not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "👋 Для начала введите <b>Фамилию Имя</b> (например: <b>Иванов Иван</b>).",
        )
        return

    if not _has_phone(u):
        await _prompt_phone_registration(message, state, back_cb="menu:root")
        return

    await show_main_menu(message.chat.id, message.from_user.id, u, "Готово. Выберите пункт меню.")

@router.message(Command("today"))
async def cmd_today(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    await show_stats_today(message.chat.id, message.from_user.id, is_admin(message), via_command=True)

@router.message(Command("my"))
async def cmd_my(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    await show_stats_week(message.chat.id, message.from_user.id, is_admin(message), via_command=True)

# Доп. команды для удобства в группах с топиками
@router.message(Command("where"))
async def cmd_where(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    # Покажем chat_id и message_thread_id, чтобы внести в .env
    tid = getattr(message, "message_thread_id", None)
    await message.answer(
        f"chat_id: <code>{message.chat.id}</code>\n"
        f"thread_id: <code>{tid if tid is not None else '-'}</code>\n"
        f"user_id: <code>{message.from_user.id}</code>")

@router.message(Command("version"))
async def cmd_version(message: Message):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    await message.answer(_runtime_version_info(message.from_user.id, message.from_user.username))

@router.message(Command("reset_ui"))
async def cmd_reset_ui(message: Message, state: FSMContext):
    """
    Админская команда: сбросить UI-стейт (menu/content message_id) и создать новое главное меню.
    Нужна, чтобы убрать накопленные старые "обрезанные" меню-сообщения после миграций UI.
    """
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        return
    await state.clear()
    # удалим саму команду пользователя (если можем) и перерисуем меню
    await _ui_try_delete_user_message(message)
    await _ui_reset(message.bot, message.chat.id, message.from_user.id)

@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    await state.clear()
    await _ui_try_delete_user_message(message)
    await _ui_reset(message.bot, message.chat.id, message.from_user.id)

@router.message(Command("purge_release"))
async def cmd_purge_release(message: Message, state: FSMContext):
    """
    Админская команда: очистить все пользовательские данные перед релизом.
    """
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, очистить", callback_data="adm:purge_release:confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:root")],
    ])
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ</b>\n"
        "Это удалит ВСЕ пользовательские данные из локальной базы:\n"
        "- регистрации (ФИО/телефон)\n"
        "- отчёты\n"
        "- роли/бригадиров\n"
        "- связи экспорта Google Sheets\n\n"
        "Справочники (локации/работы/техника) останутся.\n\n"
        "Продолжить?",
        reply_markup=kb,
    )

@router.callback_query(F.data == "adm:purge_release:confirm")
async def cb_purge_release_confirm(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.clear()
    counts = purge_release_data()
    lines = ["✅ Очищено. Удалено записей:"]
    for k in [
        "users",
        "reports",
        "user_roles",
        "brigadiers",
        "brigadier_reports",
        "google_exports",
        "monthly_sheets",
        "stat_msgs",
        "ui_state",
    ]:
        lines.append(f"- {k}: <b>{counts.get(k, 0)}</b>")
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "\n".join(lines),
        reply_markup=admin_menu_kb() if is_admin(c) else _ui_back_to_root_kb(),
    )
    await c.answer("Готово")

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    u = get_user(message.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите <b>Фамилию Имя</b> для регистрации (например: <b>Иванов Иван</b>).",
        )
        return
    if not _has_phone(u):
        await _prompt_phone_registration(message, state, back_cb="menu:root")
        return
    
    # Стараемся удалить команду пользователя, чтобы не плодить мусор
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    
    await show_main_menu(message.chat.id, message.from_user.id, u, "Меню")

@router.message(Command("phone"))
async def cmd_phone(message: Message, state: FSMContext):
    if not _is_allowed_topic(message):
        return
    await state.clear()
    await _prompt_phone_registration(message, state, back_cb="menu:root")

@router.message(Command("it"))
async def cmd_it_menu(message: Message):
    if not _is_allowed_topic(message):
        return
    if not (is_it(message.from_user.id, message.from_user.username) or is_admin(message)):
        await message.answer("Нет прав")
        return
    # убираем команду, чтобы не засорять чат
    await _ui_try_delete_user_message(message)
    u = get_user(message.from_user.id)
    name = (u or {}).get("full_name") or "—"
    text = f"👋 Привет, <b>{name}</b> (IT)!\n\nВыберите действие:"
    await _ui_ensure_main_menu(message.bot, message.chat.id, message.from_user.id)
    await _ui_edit_content(message.bot, message.chat.id, message.from_user.id, text, reply_markup=main_menu_kb("it"))

@router.message(Command("brig"))
@router.message(Command("briq"))  # частая опечатка
async def cmd_brig_menu(message: Message):
    if not _is_allowed_topic(message):
        return
    if not (is_brigadier(message.from_user.id, message.from_user.username) or is_admin(message)):
        await message.answer("Нет прав")
        return
    # убираем команду, чтобы не засорять чат
    await _ui_try_delete_user_message(message)
    u = get_user(message.from_user.id)
    name = (u or {}).get("full_name") or "—"
    text = f"👋 Привет, <b>{name}</b> (бригадир)!\n\nВыберите действие:"
    await _ui_ensure_main_menu(message.bot, message.chat.id, message.from_user.id)
    await _ui_edit_content(message.bot, message.chat.id, message.from_user.id, text, reply_markup=main_menu_kb("brigadier"))

@router.message(Command("addrole"))
async def cmd_add_role(message: Message):
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        await message.answer("Нет прав")
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Используйте: /addrole <user_id> <role>, роли: it | tim | brigadier")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом")
        return
    role = parts[2].lower()
    if role not in {"it", "tim", "brigadier"}:
        await message.answer("Роль должна быть it | tim | brigadier")
        return
    set_role(target_id, role, message.from_user.id)
    # синхронизируем бригадиров
    if role == "brigadier":
        add_brigadier(target_id, None, None, message.from_user.id)
    await message.answer(f"Роль '{role}' назначена пользователю {target_id}")

@router.message(Command("delrole"))
async def cmd_del_role(message: Message):
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        await message.answer("Нет прав")
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Используйте: /delrole <user_id> [role]")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом")
        return
    role = parts[2].lower() if len(parts) > 2 else None
    ok = clear_role(target_id, role)
    if role == "brigadier":
        remove_brigadier(target_id)
    await message.answer("Удалено" if ok else "Не найдено")

@router.message(Command("roles"))
async def cmd_list_roles(message: Message):
    if not _is_allowed_topic(message):
        return
    if not is_admin(message):
        await message.answer("Нет прав")
        return
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("SELECT user_id, role, added_by, added_at FROM user_roles ORDER BY role, user_id").fetchall()
    if not rows:
        await message.answer("Ролей нет")
        return
    lines = ["Текущие роли:"]
    for uid, role, added_by, added_at in rows:
        lines.append(f"{role}: {uid} (by {added_by} at {added_at})")
    await message.answer("\n".join(lines))

@router.message(F.text.in_({"🧰 Меню", "🔄 Сброс"}))
async def msg_persistent_menu(message: Message, state: FSMContext):
    # В read-only чате не реагируем (и по возможности удаляем сообщение работяги)
    if READONLY_CHAT_ID is not None and message.chat.id == READONLY_CHAT_ID:
        if _is_regular_user_message(message):
            try:
                await message.bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
        return
    # Нижняя кнопка теперь — "аварийный reset UI". Для совместимости принимаем и старый текст "🧰 Меню".
    await state.clear()
    await _ui_try_delete_user_message(message)
    await _ui_reset(message.bot, message.chat.id, message.from_user.id)

# Удалены лишние обработчики кнопок постоянной клавиатуры

# -------------- Регистрация --------------

@router.message(NameFSM.waiting_name)
async def capture_full_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    from_settings = data.get("name_change_from_settings")
    back_cb = "menu:name" if from_settings else "menu:root"
    if len(text) < 3 or " " not in text:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите Фамилию и Имя (через пробел). Пример: <b>Иванов Иван</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]
            ])
        )
        return
    
    # Проверяем, был ли пользователь уже зарегистрирован
    old_user = get_user(message.from_user.id)
    is_new_user = not old_user or not (old_user.get("full_name") or "").strip()
    
    # Обновляем/создаем пользователя
    upsert_user(message.from_user.id, text, TZ, message.from_user.username or "")
    u = get_user(message.from_user.id)
    await state.clear()
    
    # После ФИО — просим телефон (нужен для Google Sheets UserID)
    if not _has_phone(u):
        await _prompt_phone_registration(message, state, back_cb=back_cb)
        return

    if is_new_user:
        await show_main_menu(message.chat.id, message.from_user.id, u, f"✅ Зарегистрировано как: <b>{text}</b>")
    else:
        await show_main_menu(message.chat.id, message.from_user.id, u, f"✏️ Имя изменено на: <b>{text}</b>")

# -------------- Рисовалки экранов --------------

async def show_main_menu(chat_id:int, user_id:int, u:dict, header:str):
    # В схеме UI:
    # - 1-е сообщение: статичное "приветствие" + ReplyKeyboard (🔄 Сброс)
    # - 2-е сообщение: контент/подменю с InlineKeyboard
    await _ui_ensure_main_menu(bot, chat_id, user_id)
    role = get_role_label(user_id)
    await _ui_edit_content(bot, chat_id, user_id, "Выберите действие:", reply_markup=main_menu_kb(role))

async def show_settings_menu(bot: Bot, chat_id:int, user_id:int, header:str="Здесь вы можете сменить ФИО."):
    await _edit_or_send(bot, chat_id, user_id, header, reply_markup=settings_menu_kb())

async def show_stats_today(chat_id:int, user_id:int, admin:bool, via_command=False):
    await show_stats_period(chat_id, user_id, "today")

async def show_stats_week(chat_id:int, user_id:int, admin:bool, via_command=False):
    await show_stats_period(chat_id, user_id, "week")

def _stats_period_label(period: str, start: date, end: date) -> str:
    if period == "today":
        return "сегодня"
    if period == "week":
        return f"неделю ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"
    if period == "month":
        return f"месяц ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"
    return f"период ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"

def _stats_period_menu_kb(role: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="stats:today")
    kb.button(text="Неделя", callback_data="stats:week")
    kb.button(text="Месяц", callback_data="stats:month")
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    kb.adjust(3)
    return kb.as_markup()

def _is_admin_user_id(user_id: int) -> bool:
    # admin определяется через ADMIN_IDS / ADMIN_USERNAMES (get_role_label)
    return get_role_label(user_id) == "admin"

def _render_admin_otd(rows: list, period: str, start: date, end: date) -> str:
    """
    rows: list of tuples (full_name, username, work_date, location, activity, hours_sum)
    """
    period_str = _stats_period_label(period, start, end)
    if not rows:
        return f"📊 <b>ОТД</b> за {period_str}: нет записей."
    parts = [f"📊 <b>ОТД</b> за {period_str}:"]
    cur_user = None
    subtotal = 0
    for full_name, uname, d, loc, act, h in rows:
        who = full_name or (uname and "@"+uname) or "—"
        if who != cur_user:
            if cur_user is not None:
                parts.append(f"  — Итого сотрудник: <b>{subtotal}</b> ч\n")
            cur_user = who
            subtotal = 0
            parts.append(f"\n👤 <b>{who}</b>")
        parts.append(f"  • {d} | {loc} — {act}: <b>{h}</b> ч")
        subtotal += h
    if cur_user is not None:
        parts.append(f"  — Итого сотрудник: <b>{subtotal}</b> ч")
    return "\n".join(parts)

async def show_stats_period(chat_id: int, user_id: int, period: str) -> None:
    role = get_role_label(user_id)
    start, end = _stats_period_range(period)

    if role == "brigadier":
        ob_stats = fetch_brig_stats(user_id, start, end)
        otd_rows = fetch_stats_range_for_user(user_id, start.isoformat(), end.isoformat())
        text = _render_brig_stats_ob(ob_stats, period, start, end) + "\n\n" + _render_brig_stats_otd(otd_rows, period, start, end)
        await _edit_or_send(bot, chat_id, user_id, text, reply_markup=_stats_result_kb(role=role, period=period))
        return

    if role == "admin":
        rows = fetch_stats_range_all_with_uid(start.isoformat(), end.isoformat())
        text = _render_admin_otd_stats(rows, period, start, end)
        await _edit_or_send(bot, chat_id, user_id, text, reply_markup=_stats_result_kb(role=role, period=period))
        return

    # обычный пользователь / IT / TIM: показываем ОТД в одном формате (как у бригадиров)
    otd_rows = fetch_stats_range_for_user(user_id, start.isoformat(), end.isoformat())
    text = _render_brig_stats_otd(otd_rows, period, start, end)
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=_stats_result_kb(role=role, period=period))

# -------------- Меню --------------

def _format_otd_summary(work: dict) -> str:
    lines = ["📋 <b>Проверьте данные</b>", ""]
    lines.append(f"1. Дата - {work.get('work_date', '—')}")
    lines.append(f"2. Часы - {work.get('hours', '—')}")
    machine_type = work.get("machine_type") or ("Ручная" if work.get("act_grp") == GROUP_HAND else "—")
    lines.append(f"3. {machine_type}")
    machine_name = work.get("machine_name") or "—"
    lines.append(f"4. {machine_name}")
    location = work.get("location") or "—"
    # Для КамАЗа (machine_mode=single) "Работа" не выбирается — показываем груз вместо культуры.
    if work.get("machine_mode") == "single":
        lines.append(f"5. Груз - {work.get('crop', '—')}")
        lines.append(f"6. Место погрузки - {location}")
        lines.append(f"7. Рейсов - {work.get('trips') or 0}")
    else:
        lines.append(f"5. Работа - {work.get('activity', '—')}")
        lines.append(f"6. Культура - {work.get('crop', '—')}")
        lines.append(f"7. Место - {location}")
    return "\n".join(lines)

def _format_otd_summary_with_title(work: dict, title: str) -> str:
    # Универсальный форматтер для подтверждения/итогового экрана
    lines = [title, ""]
    lines.append(f"1. Дата - {work.get('work_date', '—')}")
    lines.append(f"2. Часы - {work.get('hours', '—')}")
    machine_type = work.get("machine_type") or ("Ручная" if work.get("act_grp") == GROUP_HAND else "—")
    lines.append(f"3. {machine_type}")
    machine_name = work.get("machine_name") or "—"
    lines.append(f"4. {machine_name}")
    location = work.get("location") or "—"
    if work.get("machine_mode") == "single":
        lines.append(f"5. Груз - {work.get('crop', '—')}")
        lines.append(f"6. Место погрузки - {location}")
        lines.append(f"7. Рейсов - {work.get('trips') or 0}")
    else:
        lines.append(f"5. Работа - {work.get('activity', '—')}")
        lines.append(f"6. Культура - {work.get('crop', '—')}")
        lines.append(f"7. Место - {location}")
    return "\n".join(lines)

@router.callback_query(F.data == "menu:root")
async def cb_menu_root(c: CallbackQuery, state: FSMContext):
    await state.clear()  # очень важно: выходим из любого состояния
    await c.answer()  # закрыть «часики»
    await show_main_menu(
        c.message.chat.id,
        c.from_user.id,
        get_user(c.from_user.id) or {},
        "",
    )

# Обработчик кнопки Start удален - теперь обычные пользователи сразу видят полное меню

@router.callback_query(F.data == "menu:work")
async def cb_menu_work(c: CallbackQuery, state: FSMContext):
    u = await _require_profile(c, state, back_cb="menu:root")
    if not u:
        return
    
    # Определяем права администратора для выбора правильной клавиатуры
    class Dummy: pass
    dummy = Dummy()
    dummy.from_user = Dummy()
    dummy.from_user.id = c.from_user.id
    dummy.from_user.username = (u or {}).get("username")
    admin = is_admin(dummy)
    
    await state.update_data(work={})
    await state.set_state(WorkFSM.pick_group)
    
    # Используем соответствующую клавиатуру в зависимости от прав
    keyboard = work_groups_kb() if admin else work_groups_kb_user()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>тип работы</b>:", reply_markup=keyboard)
    await c.answer()

@router.callback_query(F.data == "menu:stats")
async def cb_menu_stats(c: CallbackQuery):
    role = get_role_label(c.from_user.id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Выберите период статистики:",
        reply_markup=_stats_period_menu_kb(role),
    )
    await c.answer()

# ---------------- ОТД (новый поток для работяг) ----------------

async def _otd_require_user(message_or_cb, state: FSMContext) -> Optional[dict]:
    return await _require_profile(message_or_cb, state, back_cb="menu:root")

async def _otd_to_confirm(bot: Bot, chat_id: int, user_id: int, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    text = _format_otd_summary(work)
    await state.set_state(OtdFSM.confirm)
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=otd_confirm_kb())

@router.callback_query(F.data == "otd:start")
async def otd_start(c: CallbackQuery, state: FSMContext):
    u = await _otd_require_user(c, state)
    if not u:
        return
    await state.clear()
    await state.update_data(otd={"reg_name": u.get("full_name"), "username": u.get("username"), "act_grp": None})
    await state.set_state(OtdFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "ОТД: выберите дату:", reply_markup=otd_days_keyboard())
    await c.answer()

@router.callback_query(F.data == "otd:back:date")
async def otd_back_date(c: CallbackQuery, state: FSMContext):
    await state.set_state(OtdFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "ОТД: выберите дату:", reply_markup=otd_days_keyboard())
    await c.answer()

@router.callback_query(F.data == "otd:back:hours")
async def otd_back_hours(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    work.pop("hours", None)
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_hours)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите часы (можно кнопками):", reply_markup=otd_hours_keyboard())
    await c.answer()

@router.callback_query(F.data == "otd:back:type")
async def otd_back_type(c: CallbackQuery, state: FSMContext):
    await state.set_state(OtdFSM.pick_type)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите тип работы:", reply_markup=otd_type_keyboard())
    await c.answer()

@router.callback_query(F.data == "otd:back:mkind")
async def otd_back_mkind(c: CallbackQuery, state: FSMContext):
    await state.set_state(OtdFSM.pick_machine_type)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите технику:", reply_markup=otd_machine_type_kb())
    await c.answer()

@router.callback_query(F.data == "otd:back:tractor")
async def otd_back_tractor(c: CallbackQuery, state: FSMContext):
    await state.set_state(OtdFSM.pick_machine)
    data = await state.get_data()
    kind_id = data.get("otd_machine_kind_id")
    mk = get_machine_kind(int(kind_id)) if kind_id else None
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Выберите технику ({(mk or {}).get('title') or '—'}):",
                        reply_markup=otd_machine_name_kb(int(kind_id) if kind_id else 1))
    await c.answer()

@router.callback_query(F.data == "otd:back:fieldprev")
async def otd_back_field(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    back = data.get("otd", {}).get("field_back")
    if back == "trips":
        await state.set_state(OtdFSM.pick_trips)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите количество рейсов (число):")
    else:
        # по умолчанию возвращаемся к выбору работы (трактор)
        await state.set_state(OtdFSM.pick_activity)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид деятельности трактора:", reply_markup=otd_tractor_work_kb())
    await c.answer()

@router.callback_query(F.data == "otd:back:loc_or_work")
async def otd_back_loc_or_work(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    if work.get("machine_mode") == "single" and work.get("trips") is not None:
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Где погружались?", reply_markup=otd_fields_kb("otd:load"))
    elif work.get("act_grp") == GROUP_TECH and work.get("machine_mode") != "single":
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите поле:", reply_markup=otd_fields_kb("otd:field"))
    elif work.get("act_grp") == GROUP_HAND:
        await state.set_state(OtdFSM.pick_activity)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид работы:", reply_markup=otd_hand_work_kb())
    else:
        await otd_back_type(c, state)
    await c.answer()

@router.callback_query(F.data.startswith("otd:date:"))
async def otd_pick_date(c: CallbackQuery, state: FSMContext):
    d = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    work["work_date"] = d
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_hours)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите часы (можно кнопками):", reply_markup=otd_hours_keyboard())
    await c.answer()

async def _otd_set_hours(bot: Bot, chat_id: int, user_id: int, state: FSMContext, hours: int) -> tuple[bool, Optional[str]]:
    if hours < 1 or hours > 24:
        await _edit_or_send(bot, chat_id, user_id, "Часы должны быть от 1 до 24. Введите снова:",
                            reply_markup=otd_hours_keyboard())
        return False, "Часы должны быть от 1 до 24."
    data = await state.get_data()
    work = data.get("otd", {})
    # проверка лимита 24 часа сразу на этапе ввода часов
    if work.get("work_date"):
        already = sum_hours_for_user_date(user_id, work["work_date"])
        if already + hours > 24:
            await _edit_or_send(
                bot, chat_id, user_id,
                f"❗ В сутки нельзя больше 24 ч.\nНа {work['work_date']} уже учтено {already} ч. Выберите другое количество:",
                reply_markup=otd_hours_keyboard()
            )
            return False, "В сутки нельзя больше 24 ч."
    work["hours"] = hours
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_type)
    await _edit_or_send(bot, chat_id, user_id,
                        "Выберите тип работы:", reply_markup=otd_type_keyboard())
    return True, None

@router.callback_query(F.data.startswith("otd:hours:"))
async def otd_pick_hours_cb(c: CallbackQuery, state: FSMContext):
    hours = int(c.data.split(":", 2)[2])
    ok, alert = await _otd_set_hours(c.bot, c.message.chat.id, c.from_user.id, state, hours)
    if alert and not ok:
        await c.answer(alert, show_alert=True)
    else:
        await c.answer()

@router.message(OtdFSM.pick_hours)
async def otd_pick_hours_msg(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    try:
        hours = int((message.text or "").strip())
    except ValueError:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите число часов (1-24) или нажмите кнопку.",
            reply_markup=otd_hours_keyboard(),
        )
        return
    ok, alert = await _otd_set_hours(message.bot, message.chat.id, message.from_user.id, state, hours)
    # _otd_set_hours already updates the content message; don't send extra messages.
    if alert and not ok:
        return

@router.callback_query(F.data.startswith("otd:type:"))
async def otd_pick_type(c: CallbackQuery, state: FSMContext):
    kind = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if kind == "tech":
        work["act_grp"] = GROUP_TECH
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_machine_type)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Техника:", reply_markup=otd_machine_type_kb())
    else:
        work["act_grp"] = GROUP_HAND
        work["machine_type"] = "Ручная"
        work["machine_name"] = None
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_activity)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите работу:", reply_markup=otd_hand_work_kb())
    await c.answer()

@router.callback_query(F.data.startswith("otd:mkind:"))
async def otd_pick_machine_kind(c: CallbackQuery, state: FSMContext):
    raw_id = c.data.split(":", 2)[2]
    try:
        kind_id = int(raw_id)
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    mk = get_machine_kind(kind_id)
    if not mk:
        await c.answer("Техника не найдена", show_alert=True)
        return
    data = await state.get_data()
    work = data.get("otd", {})
    work["machine_type"] = mk["title"]
    work["machine_name"] = None
    work["machine_mode"] = mk.get("mode") or "list"
    await state.update_data(otd=work, otd_machine_kind_id=kind_id)

    if (mk.get("mode") or "list") == "single":
        work["machine_name"] = mk["title"]
        # В режиме single (КамАЗ) "вид работы" не выбирается — ставим дефолт,
        # чтобы запись в БД/статистике была консистентной.
        work["activity"] = work.get("activity") or "КамАЗ"
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_crop)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Груз:", reply_markup=otd_crops_kb(kamaz=True))
        await c.answer()
        return

    if count_machine_items(kind_id) <= 0:
        await state.set_state(OtdFSM.pick_machine_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            f"Введите технику ({mk['title']}) текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:mkind")]
                            ]))
        await c.answer()
        return

    await state.set_state(OtdFSM.pick_machine)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Выберите технику ({mk['title']}):", reply_markup=otd_machine_name_kb(kind_id))
    await c.answer()

@router.callback_query(F.data.startswith("otd:mname:"))
async def otd_pick_machine_name(c: CallbackQuery, state: FSMContext):
    parts = c.data.split(":")
    # otd:mname:<item_id>  OR  otd:mname:__other__:<kind_id>
    if len(parts) >= 4 and parts[2] == "__other__":
        await state.set_state(OtdFSM.pick_machine_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите технику текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:mkind")]
                            ]))
        await c.answer()
        return
    try:
        item_id = int(parts[2])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    it = get_machine_item(item_id)
    if not it:
        await c.answer("Техника не найдена", show_alert=True)
        return
    data = await state.get_data()
    work = data.get("otd", {})
    mk = get_machine_kind(it["kind_id"]) or {}
    work["machine_name"] = it["name"]
    work["machine_type"] = mk.get("title") or work.get("machine_type")
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_activity)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Вид деятельности техники:", reply_markup=otd_tractor_work_kb())
    await c.answer()

@router.message(OtdFSM.pick_machine_custom)
async def otd_pick_machine_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    text = (message.text or "").strip()
    if not text:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите технику.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:mkind")]
            ]),
        )
        return
    data = await state.get_data()
    work = data.get("otd", {})
    kind_id = data.get("otd_machine_kind_id")
    mk = get_machine_kind(int(kind_id)) if kind_id else None
    work["machine_type"] = (mk or {}).get("title") or work.get("machine_type")
    work["machine_name"] = text
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_activity)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Вид деятельности техники:", reply_markup=otd_tractor_work_kb())

@router.callback_query(F.data.startswith("otd:twork:"))
async def otd_pick_twork(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if act == "Прочее":
        work["act_grp"] = GROUP_TECH
        work["field_back"] = "twork"
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_activity_custom)
        await _edit_or_send(
            c.bot,
            c.message.chat.id,
            c.from_user.id,
            "Введите вид работы (свободная форма):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:actcustom")]
            ]),
        )
        await c.answer()
        return

    work["activity"] = act
    work["act_grp"] = GROUP_TECH
    work["field_back"] = "twork"
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_location)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Поле:", reply_markup=otd_fields_kb("otd:field"))
    await c.answer()

@router.callback_query(F.data.startswith("otd:field:"))
async def otd_pick_field(c: CallbackQuery, state: FSMContext):
    field = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if field == "__other__":
        work["location_custom_stage"] = "field"
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите название поля (свободная форма):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:loccustom")]
                            ]))
        await c.answer()
        return
    work["location"] = field
    work["location_grp"] = GROUP_WARE if field == "Склад" else GROUP_FIELDS
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культура:", reply_markup=otd_crops_kb(kamaz=(work.get("machine_mode") == "single")))
    await c.answer()

@router.callback_query(F.data.startswith("otd:hand:"))
async def otd_pick_hand(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if act == "Прочее":
        work["act_grp"] = GROUP_HAND
        work["machine_type"] = "Ручная"
        work["machine_name"] = None
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_activity_custom)
        await _edit_or_send(
            c.bot,
            c.message.chat.id,
            c.from_user.id,
            "Введите вид работы (свободная форма):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:actcustom")]
            ]),
        )
        await c.answer()
        return

    work["activity"] = act
    work["act_grp"] = GROUP_HAND
    work["machine_type"] = "Ручная"
    work["machine_name"] = None
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культура:", reply_markup=otd_crops_kb(kamaz=(work.get("machine_mode") == "single")))
    await c.answer()

@router.callback_query(F.data == "otd:back:actcustom")
async def otd_back_actcustom(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    if work.get("act_grp") == GROUP_TECH:
        await state.set_state(OtdFSM.pick_activity)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид деятельности трактора:", reply_markup=otd_tractor_work_kb())
    else:
        await state.set_state(OtdFSM.pick_activity)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид работы:", reply_markup=otd_hand_work_kb())
    await c.answer()

@router.message(OtdFSM.pick_activity_custom)
async def otd_pick_activity_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    act = (message.text or "").strip()
    if not act:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите вид работы текстом.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:actcustom")]
            ]),
        )
        return
    data = await state.get_data()
    work = data.get("otd", {})
    work["activity"] = act
    await state.update_data(otd=work)

    # дальше — по группе работы
    if work.get("act_grp") == GROUP_TECH:
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Поле:", reply_markup=otd_fields_kb("otd:field"))
    else:
        await state.set_state(OtdFSM.pick_crop)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Культура:", reply_markup=otd_crops_kb(kamaz=(work.get("machine_mode") == "single")))

@router.callback_query(F.data.startswith("otd:crop:"))
async def otd_pick_crop(c: CallbackQuery, state: FSMContext):
    crop = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if crop == "__other__" or (crop or "").strip() == "Прочее":
        await state.set_state(OtdFSM.pick_crop_custom)
        await _edit_or_send(
            c.bot,
            c.message.chat.id,
            c.from_user.id,
            "Введите культуру (свободная форма):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:crop")]
            ]),
        )
        await c.answer()
        return

    work["crop"] = crop
    await state.update_data(otd=work)
    if work.get("machine_type") == "КамАЗ":
        await state.set_state(OtdFSM.pick_trips)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько рейсов? Введите число:")
    elif work.get("machine_type") == "Трактор":
        await _otd_to_confirm(c.bot, c.message.chat.id, c.from_user.id, state)
    elif work.get("act_grp") == GROUP_HAND:
        work.setdefault("location", "—")
        work.setdefault("location_grp", "—")
        await state.update_data(otd=work)
        await _otd_to_confirm(c.bot, c.message.chat.id, c.from_user.id, state)
    else:
        await otd_back_type(c, state)
    await c.answer()

@router.callback_query(F.data == "otd:back:crop")
async def otd_back_crop(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    await state.set_state(OtdFSM.pick_crop)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Культура:",
        reply_markup=otd_crops_kb(kamaz=(work.get("machine_mode") == "single")),
    )
    await c.answer()

@router.message(OtdFSM.pick_crop_custom)
async def otd_pick_crop_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    crop = (message.text or "").strip()
    if not crop:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите культуру текстом.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:crop")]
            ]),
        )
        return
    data = await state.get_data()
    work = data.get("otd", {})
    work["crop"] = crop
    await state.update_data(otd=work)

    # дальше — как в otd_pick_crop
    if work.get("machine_type") == "КамАЗ":
        await state.set_state(OtdFSM.pick_trips)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Сколько рейсов? Введите число:")
    elif work.get("machine_type") == "Трактор":
        await _otd_to_confirm(message.bot, message.chat.id, message.from_user.id, state)
    elif work.get("act_grp") == GROUP_HAND:
        work.setdefault("location", "—")
        work.setdefault("location_grp", "—")
        await state.update_data(otd=work)
        await _otd_to_confirm(message.bot, message.chat.id, message.from_user.id, state)
    else:
        # в крайнем случае вернем на выбор типа
        await state.set_state(OtdFSM.pick_type)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Выберите тип работы:", reply_markup=otd_type_keyboard())

@router.message(OtdFSM.pick_trips)
async def otd_pick_trips(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Введите количество рейсов (только цифры):")
        return
    trips = int(text)
    data = await state.get_data()
    work = data.get("otd", {})
    work["trips"] = trips
    work["field_back"] = "trips"
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_location)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Место погрузки:", reply_markup=otd_fields_kb("otd:load"))

@router.callback_query(F.data.startswith("otd:load:"))
async def otd_pick_load(c: CallbackQuery, state: FSMContext):
    loc = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if loc == "__other__":
        work["location_custom_stage"] = "load"
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите место погрузки (свободная форма):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:loccustom")]
                            ]))
        await c.answer()
        return
    work["location"] = loc
    work["location_grp"] = GROUP_WARE if loc == "Склад" else GROUP_FIELDS
    await state.update_data(otd=work)
    await _otd_to_confirm(c.bot, c.message.chat.id, c.from_user.id, state)
    await c.answer()

@router.callback_query(F.data == "otd:back:loccustom")
async def otd_back_loccustom(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    stage = work.get("location_custom_stage") or "field"
    await state.set_state(OtdFSM.pick_location)
    kb = otd_fields_kb("otd:load" if stage == "load" else "otd:field")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите место:" if stage == "load" else "Выберите поле:",
                        reply_markup=kb)
    await c.answer()

@router.message(OtdFSM.pick_location)
async def otd_pick_location_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    loc = (message.text or "").strip()
    if not loc:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Введите значение текстом.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:loccustom")]
            ]),
        )
        return
    data = await state.get_data()
    work = data.get("otd", {})
    stage = work.get("location_custom_stage")
    if stage not in ("field", "load"):
        # не ждём кастомную локацию — игнор
        return
    work["location"] = loc
    work["location_grp"] = GROUP_WARE if loc == "Склад" else GROUP_FIELDS
    work.pop("location_custom_stage", None)
    await state.update_data(otd=work)
    if stage == "load":
        await _otd_to_confirm(message.bot, message.chat.id, message.from_user.id, state)
    else:
        await state.set_state(OtdFSM.pick_crop)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Культура:", reply_markup=otd_crops_kb(kamaz=(work.get("machine_mode") == "single")))

@router.callback_query(F.data == "otd:confirm:edit")
async def otd_confirm_edit(c: CallbackQuery, state: FSMContext):
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Что изменить?", reply_markup=otd_confirm_edit_kb())
    await c.answer()

@router.callback_query(F.data == "otd:confirm:back")
async def otd_confirm_back(c: CallbackQuery, state: FSMContext):
    await _otd_to_confirm(c.bot, c.message.chat.id, c.from_user.id, state)
    await c.answer()

@router.callback_query(F.data.startswith("otd:edit:"))
async def otd_edit_field(c: CallbackQuery, state: FSMContext):
    target = c.data.split(":", 2)[2]
    if target == "date":
        await state.set_state(OtdFSM.pick_date)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "ОТД: выберите дату:", reply_markup=otd_days_keyboard())
    elif target == "hours":
        await state.set_state(OtdFSM.pick_hours)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите часы (можно кнопками):", reply_markup=otd_hours_keyboard())
    else:
        await state.set_state(OtdFSM.pick_type)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите тип работы:", reply_markup=otd_type_keyboard())
    await c.answer()

@router.callback_query(F.data == "otd:confirm:ok")
async def otd_confirm_ok(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    work = data.get("otd", {})
    # Для КамАЗа (machine_mode=single) нет выбора "Работа", поэтому activity не требуем.
    if work.get("machine_mode") == "single":
        if not work.get("work_date") or not work.get("hours") or not work.get("crop"):
            await c.answer("Не все данные заполнены", show_alert=True)
            return
        if work.get("trips") is None or not (work.get("location") or "").strip():
            await c.answer("Не все данные заполнены", show_alert=True)
            return
    else:
        required = ("work_date", "hours", "activity", "crop")
        if not all(work.get(k) for k in required):
            await c.answer("Не все данные заполнены", show_alert=True)
            return
    # проверка лимита часов
    already = sum_hours_for_user_date(c.from_user.id, work["work_date"])
    if already + int(work["hours"]) > 24:
        await c.answer("За сутки больше 24 часов нельзя", show_alert=True)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            f"На {work['work_date']} уже учтено {already} ч. Выберите другое число:",
                            reply_markup=otd_hours_keyboard())
        await state.set_state(OtdFSM.pick_hours)
        return
    u = get_user(c.from_user.id) or {}
    rid = insert_report(
        user_id=c.from_user.id,
        reg_name=(u.get("full_name") or ""),
        username=(u.get("username") or ""),
        location=work.get("location") or "—",
        loc_grp=work.get("location_grp") or "—",
        activity=work.get("activity") or "—",
        act_grp=work.get("act_grp") or "—",
        work_date=work.get("work_date"),
        hours=int(work.get("hours") or 0),
        chat_id=c.message.chat.id,
        machine_type=work.get("machine_type"),
        machine_name=work.get("machine_name"),
        crop=work.get("crop"),
        trips=work.get("trips"),
    )
    try:
        await stats_notify_created(c.bot, rid)
    except Exception:
        pass
    try:
        await request_export_soon(otd=True, brig=False, reason="otd:create")
    except Exception:
        pass
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        _format_otd_summary_with_title(work, "✅✅✅ <b>Успешно сохранено</b>"),
                        reply_markup=_ui_back_to_root_kb())
    await c.answer("✅ Успешно сохранено")

def _brig_date_kb() -> InlineKeyboardMarkup:
    today = date.today()
    items: List[date] = [today]
    for i in range(1, 5):
        items.append(today - timedelta(days=i))
    def fmt(d: date) -> str:
        if d == today:
            return "Сегодня"
        elif d == today - timedelta(days=1):
            return "Вчера"
        elif d == today - timedelta(days=2):
            return "Позавчера"
        else:
            return d.strftime("%d.%m.%y")
    kb = InlineKeyboardBuilder()
    for d in items:
        kb.row(InlineKeyboardButton(text=fmt(d), callback_data=f"brig:date:{d.isoformat()}"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    return kb.as_markup()

def _brig_hours_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for h in range(1, 25):
        kb.button(text=str(h), callback_data=f"brig:hours:{h}")
    kb.adjust(6)
    kb.row(InlineKeyboardButton(text="✖️ X", callback_data="brig:skip:hours"))
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:date"))
    return kb.as_markup()

def _brig_ob_crop_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for crop in CROPS_LIST:
        kb.button(text=crop, callback_data=f"brig:crop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:hours")
    kb.adjust(2, 2)
    return kb.as_markup()

def _format_brig_ob_summary(brig: dict) -> str:
    crop = brig.get("crop")
    return (
        "📋 Подтвердите ОБ:\n"
        f"Дата: {brig.get('work_date') or '—'}\n"
        f"Культура: {crop if crop is not None else '—'}\n"
        f"Рядов: {brig.get('rows') if brig.get('rows') is not None else '—'}\n"
        f"Поле: {brig.get('field') or '—'}\n"
        f"Людей: {brig.get('workers') if brig.get('workers') is not None else '—'}\n"
        f"Мешков: {brig.get('bags') if brig.get('bags') is not None else '—'}"
    )

def _brig_ob_num_kb(back_cb: str, skip_field: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ X", callback_data=f"brig:skip:{skip_field}")
    kb.button(text="🔙 Назад", callback_data=back_cb)
    kb.adjust(1)
    return kb.as_markup()

async def _brig_ob_show_confirm(bot: Bot, chat_id: int, user_id: int, brig: dict) -> None:
    # В ОБ подтверждение всегда отправляем НОВЫМ сообщением (по требованию),
    # чтобы оно не "улетало вверх" и было самым свежим.
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
    kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
    kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
    kb.adjust(2, 1)
    await _send_new_message(bot, chat_id, user_id, _format_brig_ob_summary(brig), reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:report")
async def cb_brig_report(c: CallbackQuery, state: FSMContext):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.update_data(brig={})
    await state.set_state(BrigFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👷 Отчет бригадира\nВыберите дату:",
                        reply_markup=_brig_date_kb())
    await c.answer()

@router.callback_query(F.data.startswith("brig:date:"))
async def cb_brig_date(c: CallbackQuery, state: FSMContext):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    work_date = c.data.split(":")[2]
    # ОБ: без ввода часов (по требованию)
    await state.update_data(brig={"work_date": work_date, "ob_v2": True, "hours": None})
    await state.set_state(BrigFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{work_date}</b>\nВыберите культуру:", reply_markup=_brig_ob_crop_kb())
    await c.answer()

@router.callback_query(F.data == "brig:back:date")
async def brig_back_date(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👷 Отчет бригадира\nВыберите дату:",
                        reply_markup=_brig_date_kb())
    await c.answer()

@router.callback_query(F.data == "brig:back:hours")
async def brig_back_hours(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_hours)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{brig.get('work_date') or '—'}</b>\nСколько часов?",
                        reply_markup=_brig_hours_kb())
    await c.answer()

@router.callback_query(F.data.startswith("brig:hours:"))
async def cb_brig_hours(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    if not brig:
        await c.answer("Нет состояния", show_alert=True)
        return
    try:
        hours = int(c.data.split(":")[2])
    except Exception:
        await c.answer("Неверное значение", show_alert=True)
        return
    brig["hours"] = hours
    # маркер нового сценария ОБ
    brig["ob_v2"] = True
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=_brig_ob_crop_kb())
    await c.answer()

@router.callback_query(F.data == "brig:skip:hours")
async def brig_skip_hours(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    if not brig:
        await c.answer("Нет состояния", show_alert=True)
        return
    brig["hours"] = None
    brig["ob_v2"] = True
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=_brig_ob_crop_kb())
    await c.answer()

@router.callback_query(F.data.startswith("brig:shift:"))
async def cb_brig_shift(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    if not brig:
        await c.answer("Нет состояния", show_alert=True)
        return
    shift_code = c.data.split(":")[2]
    brig["shift"] = "Утренняя" if shift_code == "morning" else "Вечерняя"
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_mode)
    kb = InlineKeyboardBuilder()
    kb.button(text="Ручная", callback_data="brig:mode:hand")
    kb.button(text="Техника", callback_data="brig:mode:tech")
    kb.button(text="🔙 Назад", callback_data="brig:back:shift")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{brig.get('work_date')}</b>\nСмена: <b>{brig.get('shift')}</b>\nВыберите тип работы:",
                        reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:shift")
async def brig_back_shift(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_shift)
    kb = InlineKeyboardBuilder()
    kb.button(text="Утренняя", callback_data="brig:shift:morning")
    kb.button(text="Вечерняя", callback_data="brig:shift:evening")
    kb.button(text="🔙 Назад", callback_data="brig:back:date")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{brig.get('work_date') or '—'}</b>\nВыберите смену:",
                        reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("brig:mode:"))
async def brig_pick_mode(c: CallbackQuery, state: FSMContext):
    mode = c.data.split(":")[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["mode"] = mode
    await state.update_data(brig=brig)
    if mode == "hand":
        await state.set_state(BrigFSM.pick_activity)
        kb = InlineKeyboardBuilder()
        for act in BRIG_HAND_ACTIVITIES:
            kb.button(text=act, callback_data=f"brig:act:{act}")
        kb.button(text="Прочее", callback_data="brig:act:__other__")
        kb.button(text="🔙 Назад", callback_data="brig:back:mode")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид работы:", reply_markup=kb.as_markup())
    else:
        await state.set_state(BrigFSM.pick_machine_kind)
        kb = InlineKeyboardBuilder()
        for k in list_machine_kinds(limit=50, offset=0):
            kb.button(text=(k.get("title") or "—")[:64], callback_data=f"brig:mkind:{k['id']}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mode")
        kb.adjust(2,1)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите тип техники:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:mode")
async def brig_back_mode(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_mode)
    kb = InlineKeyboardBuilder()
    kb.button(text="Ручная", callback_data="brig:mode:hand")
    kb.button(text="Техника", callback_data="brig:mode:tech")
    kb.button(text="🔙 Назад", callback_data="brig:back:shift")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{brig.get('work_date')}</b>\nСмена: <b>{brig.get('shift')}</b>\nВыберите тип работы:",
                        reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("brig:mkind:"))
async def brig_pick_machine_kind(c: CallbackQuery, state: FSMContext):
    raw_id = c.data.split(":")[2]
    try:
        kind_id = int(raw_id)
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    mk = get_machine_kind(kind_id)
    if not mk:
        await c.answer("Техника не найдена", show_alert=True)
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["tech_kind_id"] = kind_id
    brig["tech_kind_title"] = mk["title"]
    brig["machine_mode"] = mk.get("mode") or "list"
    await state.update_data(brig=brig)
    if (mk.get("mode") or "list") != "single":
        await state.set_state(BrigFSM.pick_machine_name)
        kb = InlineKeyboardBuilder()
        for it in list_machine_items(kind_id, limit=50, offset=0):
            kb.button(text=(it.get("name") or "—")[:64], callback_data=f"brig:mname:{it['id']}")
        kb.button(text="Прочее", callback_data=f"brig:mname:__other__:{kind_id}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите технику:", reply_markup=kb.as_markup())
    else:
        brig["machine"] = mk["title"]
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_kamaz_crop)
        kb = InlineKeyboardBuilder()
        for name in KAMAZ_CARGO_LIST:
            kb.button(text=name, callback_data=f"brig:kcrop:{name}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            f"{mk['title']}: выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:mkind")
async def brig_back_mkind(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_machine_kind)
    kb = InlineKeyboardBuilder()
    for k in list_machine_kinds(limit=50, offset=0):
        kb.button(text=(k.get("title") or "—")[:64], callback_data=f"brig:mkind:{k['id']}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mode")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите тип техники:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("brig:mname:"))
async def brig_pick_machine_name(c: CallbackQuery, state: FSMContext):
    parts = c.data.split(":")
    name = parts[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    if name == "__other__":
        await state.set_state(BrigFSM.pick_machine_name_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите технику текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mkind")]
                            ]))
    else:
        try:
            item_id = int(name)
        except Exception:
            await c.answer("Некорректный выбор", show_alert=True)
            return
        it = get_machine_item(item_id)
        if not it:
            await c.answer("Техника не найдена", show_alert=True)
            return
        brig["machine"] = it["name"]
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_machine_activity)
        kb = InlineKeyboardBuilder()
        for act in ["Сев", "Опрыскивание", "Междурядная Культивация (МК)", "Боронование", "Уборка", "Дискование", "Пахота", "Чизелевание", "Навоз"]:
            kb.button(text=act, callback_data=f"brig:mact:{act}")
        kb.button(text="Прочее", callback_data="brig:mact:__other__")
        kb.button(text="🔙 Назад", callback_data="brig:back:mname")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид деятельности:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_machine_name_custom)
async def brig_pick_machine_name_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    name = (message.text or "").strip()
    if not name:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Название не может быть пустым",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mkind")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine"] = name
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_machine_activity)
    kb = InlineKeyboardBuilder()
    for act in ["Сев", "Опрыскивание", "Междурядная Культивация (МК)", "Боронование", "Уборка", "Дискование", "Пахота", "Чизелевание", "Навоз"]:
        kb.button(text=act, callback_data=f"brig:mact:{act}")
    kb.button(text="Прочее", callback_data="brig:mact:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:mname")
    kb.adjust(2,2)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите вид деятельности:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:back:mname")
async def brig_back_mname(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_machine_name)
    data = await state.get_data()
    brig = data.get("brig", {})
    kind_id = brig.get("tech_kind_id") or 1
    kb = InlineKeyboardBuilder()
    for it in list_machine_items(int(kind_id), limit=50, offset=0):
        kb.button(text=(it.get("name") or "—")[:64], callback_data=f"brig:mname:{it['id']}")
    kb.button(text="Прочее", callback_data=f"brig:mname:__other__:{kind_id}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите технику:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("brig:mact:"))
async def brig_pick_machine_activity(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":", 2)[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    if act == "__other__":
        await state.set_state(BrigFSM.pick_machine_activity_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите вид деятельности текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mact")]
                            ]))
    else:
        brig["machine_activity"] = act
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_machine_crop)
        kb = InlineKeyboardBuilder()
        for crop in CROPS_LIST:
            kb.button(text=crop, callback_data=f"brig:mcrop:{crop}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mact")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:mact")
async def brig_back_mact(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_machine_activity)
    kb = InlineKeyboardBuilder()
    for act in ["Сев", "Опрыскивание", "Междурядная Культивация (МК)", "Боронование", "Уборка", "Дискование", "Пахота", "Чизелевание", "Навоз"]:
        kb.button(text=act, callback_data=f"brig:mact:{act}")
    kb.button(text="Прочее", callback_data="brig:mact:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:mname")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите вид деятельности:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_machine_activity_custom)
async def brig_pick_machine_activity_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    act = (message.text or "").strip()
    if not act:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Значение не может быть пустым",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mact")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine_activity"] = act
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_machine_crop)
    kb = InlineKeyboardBuilder()
    for crop in CROPS_LIST:
        kb.button(text=crop, callback_data=f"brig:mcrop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mact")
    kb.adjust(2,2)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("brig:mcrop:"))
async def brig_pick_machine_crop(c: CallbackQuery, state: FSMContext):
    crop = c.data.split(":", 2)[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    if crop == "Прочее":
        await state.set_state(BrigFSM.pick_machine_crop_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите культуру текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mcrop")]
                            ]))
    else:
        brig["machine_crop"] = crop
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.confirm)
        brig["confirm_back"] = "tech_crop"
        await state.update_data(brig=brig)
        summary = (
            "📋 Подтвердите отчет (Техника):\n"
            f"Дата: {brig.get('work_date')}\n"
            f"Смена: {brig.get('shift')}\n"
            f"Техника: {brig.get('machine')}\n"
            f"Деятельность: {brig.get('machine_activity')}\n"
            f"Культура: {brig.get('machine_crop')}\n"
            f"Локация: —\n"
            f"Рейсов: —"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
        kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
        kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
        kb.adjust(2,1)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, summary, reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:mcrop")
async def brig_back_mcrop(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_machine_crop)
    kb = InlineKeyboardBuilder()
    for crop in CROPS_LIST:
        kb.button(text=crop, callback_data=f"brig:mcrop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mact")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_machine_crop_custom)
async def brig_pick_machine_crop_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    crop = (message.text or "").strip()
    if not crop:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Культура не может быть пустой",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:mcrop")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine_crop"] = crop
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.confirm)
    brig["confirm_back"] = "tech_crop"
    await state.update_data(brig=brig)
    summary = (
        "📋 Подтвердите отчет (Техника):\n"
        f"Дата: {brig.get('work_date')}\n"
        f"Смена: {brig.get('shift')}\n"
        f"Техника: {brig.get('machine')}\n"
        f"Деятельность: {brig.get('machine_activity')}\n"
        f"Культура: {brig.get('machine_crop')}\n"
        f"Локация: —\n"
        f"Рейсов: —"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
    kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
    kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
    kb.adjust(2,1)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, summary, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("brig:kcrop:"))
async def brig_kamaz_crop(c: CallbackQuery, state: FSMContext):
    crop = c.data.split(":", 2)[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    if crop == "Прочее":
        await state.set_state(BrigFSM.pick_kamaz_crop_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите культуру текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                            ]))
    else:
        brig["machine_crop"] = crop
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_kamaz_trips)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько рейсов?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:back:kcrop")
async def brig_back_kcrop(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_kamaz_crop)
    kb = InlineKeyboardBuilder()
    for name in KAMAZ_CARGO_LIST:
        kb.button(text=name, callback_data=f"brig:kcrop:{name}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "КамАЗ: выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_kamaz_crop_custom)
async def brig_kamaz_crop_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    crop = (message.text or "").strip()
    if not crop:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Культура не может быть пустой",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine_crop"] = crop
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_kamaz_trips)
    await _edit_or_send(
        message.bot,
        message.chat.id,
        message.from_user.id,
        "Сколько рейсов?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
        ]),
    )

@router.message(BrigFSM.pick_kamaz_trips)
async def brig_kamaz_trips(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Введите число рейсов (только цифры):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                            ]))
        return
    trips = int(text)
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["trips"] = trips
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_kamaz_load)
    kb = InlineKeyboardBuilder()
    locations = list_locations(GROUP_FIELDS)
    for loc in locations:
        kb.button(text=loc, callback_data=f"brig:kload:{loc}")
    kb.button(text="Склад", callback_data="brig:kload:Склад")
    kb.button(text="Прочее", callback_data="brig:kload:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:ktrips")
    kb.adjust(2)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Место погрузки:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:back:ktrips")
async def brig_back_ktrips(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_kamaz_trips)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Сколько рейсов?",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("brig:kload:"))
async def brig_kamaz_load(c: CallbackQuery, state: FSMContext):
    load = c.data.split(":", 2)[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    if load == "__other__":
        await state.set_state(BrigFSM.pick_kamaz_load_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите место погрузки текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kload")]
                            ]))
    else:
        brig["field"] = load
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.confirm)
        brig["confirm_back"] = "kamaz_load"
        await state.update_data(brig=brig)
        summary = (
            "📋 Подтвердите отчет (КамАЗ):\n"
            f"Дата: {brig.get('work_date')}\n"
            f"Смена: {brig.get('shift')}\n"
            f"Культура: {brig.get('machine_crop')}\n"
            f"Рейсов: {brig.get('trips')}\n"
            f"Место погрузки: {brig.get('field')}\n"
            f"Техника: КамАЗ"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
        kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
        kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
        kb.adjust(2,1)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, summary, reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:kload")
async def brig_back_kload(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_kamaz_load)
    kb = InlineKeyboardBuilder()
    locations = list_locations(GROUP_FIELDS)
    for loc in locations:
        kb.button(text=loc, callback_data=f"brig:kload:{loc}")
    kb.button(text="Склад", callback_data="brig:kload:Склад")
    kb.button(text="Прочее", callback_data="brig:kload:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:ktrips")
    kb.adjust(2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Место погрузки:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_kamaz_load_custom)
async def brig_kamaz_load_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    load = (message.text or "").strip()
    if not load:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Место не может быть пустым",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kload")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["field"] = load
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.confirm)
    brig["confirm_back"] = "kamaz_load"
    await state.update_data(brig=brig)
    summary = (
        "📋 Подтвердите отчет (КамАЗ):\n"
        f"Дата: {brig.get('work_date')}\n"
        f"Смена: {brig.get('shift')}\n"
        f"Культура: {brig.get('machine_crop')}\n"
        f"Рейсов: {brig.get('trips')}\n"
        f"Место погрузки: {brig.get('field')}\n"
        f"Техника: КамАЗ"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
    kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
    kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
    kb.adjust(2,1)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, summary, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("brig:crop:"))
async def cb_brig_crop(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    if not brig:
        await c.answer("Нет состояния", show_alert=True)
        return
    crop = c.data.split(":", 2)[2]
    brig["crop"] = crop
    await state.update_data(brig=brig)
    # Новый сценарий ОБ: после культуры -> рядов
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await state.set_state(BrigFSM.pick_rows)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите число рядов:",
                            reply_markup=_brig_ob_num_kb("brig:back:crop", "rows"))
    else:
        # Старый сценарий (на всякий случай оставляем)
        brig["mode"] = brig.get("mode") or "hand"
        await state.set_state(BrigFSM.pick_workers)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько людей работало?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:back:crop")
async def brig_back_crop(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_crop)
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите культуру:", reply_markup=_brig_ob_crop_kb())
    else:
        kb = InlineKeyboardBuilder()
        for crop in CROPS_LIST:
            kb.button(text=crop, callback_data=f"brig:crop:{crop}")
        kb.button(text="🔙 Назад", callback_data="brig:back:activity")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_crop_custom)
async def brig_pick_crop_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    crop = (message.text or "").strip()
    if not crop:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Культура не может быть пустой",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["mode"] = brig.get("mode") or "hand"
    brig["crop"] = crop
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_workers)
    await _edit_or_send(
        message.bot,
        message.chat.id,
        message.from_user.id,
        "Сколько людей работало?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
        ]),
    )

@router.callback_query(F.data.startswith("brig:act:"))
async def brig_pick_activity(c: CallbackQuery, state: FSMContext):
    _, _, act = c.data.split(":", 2)
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["activity"] = act
    await state.update_data(brig=brig)
    if act == "__other__":
        await state.set_state(BrigFSM.pick_activity_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите вид работы текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:activity")]
                            ]))
    else:
        await state.set_state(BrigFSM.pick_crop)
        kb = InlineKeyboardBuilder()
        for crop in CROPS_LIST:
            kb.button(text=crop, callback_data=f"brig:crop:{crop}")
        kb.button(text="🔙 Назад", callback_data="brig:back:activity")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_activity_custom)
async def brig_pick_activity_custom(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    act = (message.text or "").strip()
    if not act:
        await _edit_or_send(
            message.bot,
            message.chat.id,
            message.from_user.id,
            "Значение не может быть пустым",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:activity")]
            ]),
        )
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["activity"] = act
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_crop)
    kb = InlineKeyboardBuilder()
    for crop in CROPS_LIST:
        kb.button(text=crop, callback_data=f"brig:crop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:activity")
    kb.adjust(2,2)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:back:activity")
async def brig_back_activity(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_activity)
    kb = InlineKeyboardBuilder()
    for act in BRIG_HAND_ACTIVITIES:
        kb.button(text=act, callback_data=f"brig:act:{act}")
    kb.button(text="Прочее", callback_data="brig:act:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:mode")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите вид работы:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_workers)
async def brig_pick_workers(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Введите число людей (только цифры):",
                            reply_markup=_brig_ob_num_kb("brig:back:field", "workers"))
        return
    workers = int(text)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["workers"] = workers
    await state.update_data(brig=brig)
    # Новый сценарий ОБ: после людей -> мешков (для любой культуры)
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await state.set_state(BrigFSM.pick_bags)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Сколько мешков?",
                            reply_markup=_brig_ob_num_kb("brig:back:workers", "bags"))
    else:
        await state.set_state(BrigFSM.pick_rows)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Сколько рядов?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:workers")]
                            ]))

@router.callback_query(F.data == "brig:back:workers")
async def brig_back_workers(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_workers)
    data = await state.get_data()
    brig = data.get("brig", {})
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько людей работало?",
                            reply_markup=_brig_ob_num_kb("brig:back:field", "workers"))
    else:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько людей работало?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:skip:workers")
async def brig_skip_workers(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["workers"] = None
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_bags)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Сколько мешков?",
                        reply_markup=_brig_ob_num_kb("brig:back:workers", "bags"))
    await c.answer()

@router.message(BrigFSM.pick_rows)
async def brig_pick_rows(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        # удаляем ввод пользователя, чтобы не засорять чат
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Введите число рядов (только цифры):",
                            reply_markup=_brig_ob_num_kb("brig:back:crop", "rows"))
        return
    rows = int(text)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["rows"] = rows
    await state.update_data(brig=brig)
    # Новый сценарий ОБ: после рядов -> поле
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await state.set_state(BrigFSM.pick_field)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Название поля:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                            ]))
    else:
        crop = (brig.get("crop") or "").lower()
        if crop.startswith("карт"):
            await state.set_state(BrigFSM.pick_bags)
            await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                                "Сколько мешков?",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                                ]))
        else:
            await state.set_state(BrigFSM.pick_field)
            await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                                "Укажите локацию (поле/место):",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                                ]))

@router.callback_query(F.data == "brig:back:rows")
async def brig_back_rows(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_rows)
    data = await state.get_data()
    brig = data.get("brig", {})
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите число рядов:",
                            reply_markup=_brig_ob_num_kb("brig:back:crop", "rows"))
    else:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько рядов?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:workers")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:skip:rows")
async def brig_skip_rows(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["rows"] = None
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_field)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Название поля:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                        ]))
    await c.answer()

@router.message(BrigFSM.pick_bags)
async def brig_pick_bags(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Введите число мешков (только цифры):",
                            reply_markup=_brig_ob_num_kb("brig:back:workers", "bags"))
        return
    bags = int(text)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["bags"] = bags
    await state.update_data(brig=brig)
    # Новый сценарий ОБ: после мешков -> подтверждение (люди уже должны быть)
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await state.set_state(BrigFSM.confirm)
        brig["confirm_back"] = "bags_ob"
        await state.update_data(brig=brig)
        await _brig_ob_show_confirm(message.bot, message.chat.id, message.from_user.id, brig)
    else:
        await state.set_state(BrigFSM.pick_field)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Укажите локацию (поле/место):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                            ]))

@router.callback_query(F.data == "brig:back:bags")
async def brig_back_bags(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_bags)
    data = await state.get_data()
    brig = data.get("brig", {})
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько мешков?",
                            reply_markup=_brig_ob_num_kb("brig:back:workers", "bags"))
    else:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько мешков?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:skip:bags")
async def brig_skip_bags(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["bags"] = None
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.confirm)
    brig["confirm_back"] = "bags_ob"
    await state.update_data(brig=brig)
    await _brig_ob_show_confirm(c.bot, c.message.chat.id, c.from_user.id, brig)
    await c.answer()

@router.message(BrigFSM.pick_field)
async def brig_pick_field(message: Message, state: FSMContext):
    field = (message.text or "").strip()
    if not field:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "❗ Поле не может быть пустым. Введите ещё раз:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                            ]))
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["field"] = field
    await state.update_data(brig=brig)
    # Новый сценарий ОБ: после поля -> люди
    if brig.get("ob_v2") or brig.get("hours") is not None:
        await state.set_state(BrigFSM.pick_workers)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            "Сколько людей работало?",
                            reply_markup=_brig_ob_num_kb("brig:back:field", "workers"))
    else:
        await state.set_state(BrigFSM.confirm)
        brig["confirm_back"] = "field"
        await state.update_data(brig=brig)
        summary = (
            f"📋 Подтвердите отчет:\n"
            f"Дата: {brig.get('work_date')}\n"
            f"Смена: {brig.get('shift')}\n"
            f"Культура: {brig.get('crop')}\n"
            f"Вид работы: {brig.get('activity')}\n"
            f"Людей: {brig.get('workers')}\n"
            f"Рядов: {brig.get('rows')}\n"
            f"Мешков: {brig.get('bags') if (brig.get('crop') or '').lower().startswith('карт') else '—'}\n"
            f"Локация: {brig.get('field')}"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Сохранить", callback_data="brig:confirm:save")
        kb.button(text="🔙 Назад", callback_data="brig:confirm:back")
        kb.button(text="❌ Отмена", callback_data="brig:confirm:cancel")
        kb.adjust(2,1)
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, summary, reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:back:field")
async def brig_back_field(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_field)
    prompt = "Название поля:" if (brig.get("ob_v2") or brig.get("hours") is not None) else "Укажите локацию (поле/место):"
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        prompt,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                        ]))
    await c.answer()

@router.callback_query(F.data == "brig:confirm:back")
async def brig_confirm_back(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    target = brig.get("confirm_back") or "field"
    # Новый сценарий ОБ (v2)
    if brig.get("ob_v2") or brig.get("hours") is not None:
        # В новом ОБ подтверждение всегда после мешков, поэтому назад ведёт к мешкам
        await state.set_state(BrigFSM.pick_bags)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Сколько мешков?",
                            reply_markup=_brig_ob_num_kb("brig:back:workers", "bags"))
        await c.answer()
        return
    if target == "tech_crop":
        await state.set_state(BrigFSM.pick_machine_crop)
        kb = InlineKeyboardBuilder()
        for crop in CROPS_LIST:
            kb.button(text=crop, callback_data=f"brig:mcrop:{crop}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mact")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите культуру:", reply_markup=kb.as_markup())
    elif target == "kamaz_load":
        await state.set_state(BrigFSM.pick_kamaz_load)
        kb = InlineKeyboardBuilder()
        locations = list_locations(GROUP_FIELDS)
        for loc in locations:
            kb.button(text=loc, callback_data=f"brig:kload:{loc}")
        kb.button(text="Склад", callback_data="brig:kload:Склад")
        kb.button(text="Прочее", callback_data="brig:kload:__other__")
        kb.button(text="🔙 Назад", callback_data="brig:back:ktrips")
        kb.adjust(2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Место погрузки:", reply_markup=kb.as_markup())
    else:
        await state.set_state(BrigFSM.pick_field)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Укажите локацию (поле/место):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                            ]))
    await c.answer()

@router.callback_query(F.data == "brig:confirm:save")
async def brig_confirm_save(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    if not brig:
        await c.answer("Нет данных", show_alert=True)
        return
    # Новый сценарий ОБ (v2)
    if brig.get("ob_v2") or brig.get("hours") is not None:
        u = get_user(c.from_user.id) or {}
        username = (u.get("username") or c.from_user.username or "")
        work_type = brig.get("crop") or "—"
        field = brig.get("field") or "—"
        shift = "—"
        rows = brig.get("rows")
        workers = brig.get("workers")
        bags = brig.get("bags")
        work_date = brig.get("work_date") or date.today().isoformat()
        insert_brig_report(
            user_id=c.from_user.id,
            username=username,
            work_type=work_type,
            field=field,
            shift=shift,
            rows=rows,
            bags=bags,
            workers=workers,
            work_date=work_date,
        )
        try:
            await request_export_soon(otd=False, brig=True, reason="brig:create")
        except Exception:
            pass
        await state.clear()
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "✅ ОБ сохранено",
                            reply_markup=_ui_back_to_root_kb())
        await c.answer("Сохранено")
        return
    mode = brig.get("mode") or "hand"
    if mode == "tech":
        if brig.get("tech_kind") == "tractor":
            work_type = f"{brig.get('machine_crop') or 'Прочее'} (техника: {brig.get('machine')}; {brig.get('machine_activity')})"
            field = "—"
            rows = bags = workers = 0
        else:
            work_type = f"{brig.get('machine_crop') or 'Прочее'} (КамАЗ, рейсов: {brig.get('trips') or 0})"
            field = brig.get("field") or "—"
            rows = bags = workers = 0
    else:
        work_type = brig.get("crop") or "Прочее"
        activity = brig.get("activity")
        if activity:
            work_type = f"{work_type} — {activity}"
        field = brig.get("field") or "—"
        rows = int(brig.get("rows") or 0)
        bags = int(brig.get("bags") or 0)
        workers = int(brig.get("workers") or 0)
    insert_brig_report(
        user_id=c.from_user.id,
        username=c.from_user.username,
        work_type=work_type,
        field=field,
        shift=brig.get("shift") or "—",
        rows=rows,
        bags=bags,
        workers=workers,
        work_date=brig.get("work_date") or date.today().isoformat(),
    )
    try:
        await request_export_soon(otd=False, brig=True, reason="brig:create")
    except Exception:
        pass
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "✅ Отчет бригадира сохранен", reply_markup=_ui_back_to_root_kb())
    await c.answer("Сохранено")

@router.callback_query(F.data == "brig:confirm:cancel")
async def brig_confirm_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "Отчет отменен", reply_markup=_ui_back_to_root_kb())
    await c.answer()

@router.callback_query(F.data == "brig:stats")
async def brig_stats_menu(c: CallbackQuery):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    # Совместимость со старой кнопкой бригадира — теперь ведём в общий экран статистики
    await cb_menu_stats(c)
    await c.answer()

def _render_brig_stats_ob(stats: dict, period: str, start: date, end: date) -> str:
    period_str = _stats_period_label(period, start, end)
    lines = [f"📊 <b>ОБ</b> за {period_str}:"]
    by_crop = stats.get("by_crop") or {}
    if by_crop:
        # стабильный порядок: сначала известные культуры из списка, потом остальное
        ordered = []
        for c in CROPS_LIST + ["Навоз"]:
            if c in by_crop:
                ordered.append(c)
        for c in sorted(by_crop.keys()):
            if c not in ordered:
                ordered.append(c)
        for c in ordered:
            v = by_crop.get(c) or {}
            lines.append(f"• {c}: рядов {v.get('rows',0)}, мешков {v.get('bags',0)}, людей {v.get('workers',0)}")
    if stats.get("details"):
        lines.append("\nДетали:")
        lines.extend((stats["details"] or [])[:10])
    if len(lines) == 1:
        lines.append("Нет данных")
    return "\n".join(lines)

def _render_brig_stats_otd(rows: list, period: str, start: date, end: date) -> str:
    if period == "today":
        period_str = "сегодня"
    elif period == "month":
        period_str = f"месяц ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"
    else:
        period_str = f"неделю ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"
    if not rows:
        return f"📊 <b>ОТД</b> за {period_str}: нет записей."
    parts = [f"📊 <b>ОТД</b> за {period_str}:"]
    per_day = {}
    total = 0
    for d, loc, act, h in rows:
        per_day.setdefault(d, []).append((loc, act, h))
    for d in sorted(per_day.keys(), reverse=True):
        parts.append(f"\n<b>{d}</b>")
        for loc, act, h in per_day[d]:
            parts.append(f"• {loc} — {act}: <b>{h}</b> ч")
            total += h
    parts.append(f"\nИтого: <b>{total}</b> ч")
    return "\n".join(parts)

def _stats_period_range(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "today":
        return today, today
    if period == "month":
        start = today.replace(day=1)
        # последний день месяца
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end
    # week (по умолчанию)
    return today - timedelta(days=6), today

def _render_admin_otd_stats(rows: list, period: str, start: date, end: date) -> str:
    """
    rows: (user_id, full_name, username, work_date, location, activity, h)
    """
    if period == "today":
        period_str = "сегодня"
    elif period == "month":
        period_str = f"месяц ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"
    else:
        period_str = f"неделю ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})"

    if not rows:
        return f"📊 <b>ОТД</b> за {period_str}: нет записей."

    # group: user -> date -> list
    by_user: dict[int, dict] = {}
    for uid, full_name, uname, d, loc, act, h in rows:
        u = by_user.setdefault(int(uid), {"name": (full_name or (uname and "@"+uname) or str(uid)), "days": {}})
        u["days"].setdefault(d, []).append((loc, act, int(h or 0)))

    lines = [f"📊 <b>ОТД</b> за {period_str}:"]
    total_all = 0
    # стабильная сортировка по имени
    ordered_users = sorted(by_user.items(), key=lambda kv: (kv[1].get("name") or "").lower())
    for _, u in ordered_users:
        lines.append(f"\n👤 <b>{html.escape(str(u.get('name') or '—'))}</b>")
        subtotal = 0
        days = u.get("days") or {}
        for d in sorted(days.keys(), reverse=True):
            lines.append(f"\n<b>{d}</b>")
            for loc, act, h in days[d]:
                lines.append(f"• {loc} — {act}: <b>{h}</b> ч")
                subtotal += h
        lines.append(f"\n— Итого сотрудник: <b>{subtotal}</b> ч")
        total_all += subtotal

    lines.append(f"\nИтого всего: <b>{total_all}</b> ч")
    return "\n".join(lines)

def _stats_result_kb(*, role: str, period: str) -> InlineKeyboardMarkup:
    # Явная разметка клавиатуры (без билдера), чтобы гарантированно рисовались все строки.
    first_row = (
        InlineKeyboardButton(text="✏️ Изменить / удалить", callback_data=f"adm:stats:edit:{period}")
        if role == "admin"
        else InlineKeyboardButton(text="✏️ Изменить / удалить", callback_data="menu:edit")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [first_row],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:stats")],
            [InlineKeyboardButton(text="🧰 В меню", callback_data="menu:root")],
        ]
    )

@router.callback_query(F.data.startswith("brig:stats:"))
async def brig_stats_show(c: CallbackQuery):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    # Совместимость со старыми callback'ами бригадира
    period = c.data.split(":")[2]
    await show_stats_period(c.message.chat.id, c.from_user.id, period)
    await c.answer()

@router.callback_query(F.data == "tim:party")
async def tim_party(c: CallbackQuery):
    if not is_tim(c.from_user.id):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👀 Режим наблюдения TIM активен. Доступны: статистика и смена имени.",
                        reply_markup=_ui_back_to_root_kb())
    await c.answer()

@router.callback_query(F.data == "it:star")
async def it_star(c: CallbackQuery):
    if not (is_it(c.from_user.id, c.from_user.username) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "⭐ IT панель: используйте /menu для полного списка. Статистика доступна в меню.",
                        reply_markup=_ui_back_to_root_kb())
    await c.answer()

@router.callback_query(F.data == "menu:edit")
async def cb_menu_edit(c: CallbackQuery):
    await _send_user_edit_menu_by_id(c.bot, c.message.chat.id, c.from_user.id)
    await c.answer()

async def _send_user_edit_menu_by_id(bot: Bot, chat_id: int, user_id: int) -> None:
    rows = user_recent_24h_reports(user_id)
    if not rows:
        await _send_new_message(
            bot,
            chat_id,
            user_id,
            "📝 За последние 48 часов записей нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")]]),
        )
        return

    kb = InlineKeyboardBuilder()
    text = ["📝 <b>Ваши записи за последние 48 часов</b>:"]
    for rid, d, act, loc, h, created, mtype, mname, crop, trips in rows:
        extra = []
        if crop:
            extra.append(f"культура: {crop}")
        if mtype:
            extra.append(mtype if not mname else f"{mtype} {mname}")
        if trips:
            extra.append(f"рейсов: {trips}")
        extra_str = f" ({'; '.join(extra)})" if extra else ""
        text.append(f"• #{rid} {d} | {loc} — {act}: <b>{h}</b> ч{extra_str}")
        kb.row(
            InlineKeyboardButton(text=f"🖊 Изменить #{rid}", callback_data=f"edit:chg:{rid}:{d}"),
            InlineKeyboardButton(text=f"🗑 Удалить #{rid}", callback_data=f"edit:del:{rid}"),
        )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    await _send_new_message(bot, chat_id, user_id, "\n".join(text), reply_markup=kb.as_markup())

async def _edit_state_clear_preserve_return(state: FSMContext) -> None:
    data = await state.get_data()
    keep = {k: v for k, v in (data or {}).items() if k.startswith("edit_return_")}
    await state.clear()
    if keep:
        await state.update_data(**keep)

@router.callback_query(F.data == "menu:admin")
async def cb_menu_admin(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "⚙️ <b>Админ-панель</b>:", reply_markup=admin_menu_kb())
    await c.answer()

@router.callback_query(F.data == "adm:root")
async def adm_root(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Админ: выберите раздел:", reply_markup=admin_root_kb())
    await c.answer()

@router.callback_query(F.data == "adm:root:loc")
async def adm_root_loc(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Локации: выберите локацию:", reply_markup=admin_root_loc_list_kb(page=0))
    await c.answer()

@router.callback_query(F.data == "adm:root:act")
async def adm_root_act(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Работа: выберите тип работ:", reply_markup=admin_root_act_pick_grp_kb())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:loc:page:"))
async def adm_root_loc_page(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        page = int(c.data.rsplit(":", 1)[1])
    except Exception:
        page = 0
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Локации: выберите локацию:", reply_markup=admin_root_loc_list_kb(page=page))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:loc:item:"))
async def adm_root_loc_item(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        loc_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    loc = get_location_by_id(loc_id)
    if not loc:
        await c.answer("Локация не найдена", show_alert=True)
        return
    grp = loc.get("grp") or ""
    grp_lbl = "поля" if grp == GROUP_FIELDS else ("склад" if grp == GROUP_WARE else grp)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Локация: <b>{loc['name']}</b> ({grp_lbl})", reply_markup=admin_root_loc_item_kb(loc_id))
    await c.answer()

@router.callback_query(F.data == "adm:root:loc:add")
async def adm_root_loc_add(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Добавить локацию: выберите группу", reply_markup=admin_root_loc_add_grp_kb())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:loc:addgrp:"))
async def adm_root_loc_addgrp(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    grp = c.data.rsplit(":", 1)[1]  # fields/ware
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="loc", admin_grp=grp, admin_done="adm:root:loc")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название локации:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:loc:add")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:loc:edit:"))
async def adm_root_loc_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        loc_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    loc = get_location_by_id(loc_id)
    if not loc:
        await c.answer("Локация не найдена", show_alert=True)
        return
    await state.set_state(AdminFSM.edit_name)
    await state.update_data(edit_kind="loc", edit_id=loc_id, edit_return="adm:root:loc")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите новое название локации:\n\nТекущее: <b>{loc['name']}</b>",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm:root:loc:item:{loc_id}")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:loc:del:"))
async def adm_root_loc_del(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        loc_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    loc = get_location_by_id(loc_id)
    if not loc:
        await c.answer("Локация не найдена", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm:confirm:del:loc:{loc_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:root:loc:item:{loc_id}")]
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Точно удалить локацию <b>{loc['name']}</b>?",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:grp:"))
async def adm_root_act_grp(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    grp = c.data.rsplit(":", 1)[1]  # tech/hand
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Работа: выберите элемент:", reply_markup=admin_root_act_list_kb(grp, page=0))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:page:"))
async def adm_root_act_page(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    grp = parts[4]
    try:
        page = int(parts[5])
    except Exception:
        page = 0
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Работа: выберите элемент:", reply_markup=admin_root_act_list_kb(grp, page=page))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:item:"))
async def adm_root_act_item(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    grp = parts[4]
    try:
        act_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    act = get_activity_by_id(act_id)
    if not act:
        await c.answer("Элемент не найден", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Работа ({'техника' if grp=='tech' else 'ручная'}): <b>{act['name']}</b>",
                        reply_markup=admin_root_act_item_kb(grp, act_id))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:add:"))
async def adm_root_act_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    grp = c.data.rsplit(":", 1)[1]  # tech/hand
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="act", admin_grp=grp, admin_done=f"adm:root:act:grp:{grp}")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название работы:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm:root:act:grp:{grp}")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:edit:"))
async def adm_root_act_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    grp = parts[4]
    try:
        act_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    act = get_activity_by_id(act_id)
    if not act:
        await c.answer("Элемент не найден", show_alert=True)
        return
    await state.set_state(AdminFSM.edit_name)
    await state.update_data(edit_kind="act", edit_id=act_id, edit_grp=grp, edit_return=f"adm:root:act:item:{grp}:{act_id}")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите новое название работы:\n\nТекущее: <b>{act['name']}</b>",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm:root:act:item:{grp}:{act_id}")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:act:del:"))
async def adm_root_act_del(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    grp = parts[4]
    try:
        act_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    act = get_activity_by_id(act_id)
    if not act:
        await c.answer("Элемент не найден", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm:confirm:del:act:{grp}:{act_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:root:act:item:{grp}:{act_id}")]
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Точно удалить работу <b>{act['name']}</b>?",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data == "adm:root:tech")
async def adm_root_tech(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Техника: выберите раздел:", reply_markup=admin_root_tech_kb())
    await c.answer()

@router.callback_query(F.data == "adm:root:tech:tractor")
async def adm_root_tech_tractor(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Трактор: выберите технику:", reply_markup=admin_root_tech_items_kb(1, page=0))
    await c.answer()

@router.callback_query(F.data == "adm:root:tech:kamaz")
async def adm_root_tech_kamaz(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "КамАЗ:", reply_markup=admin_root_tech_kamaz_kb())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:page:"))
async def adm_root_tech_page(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    try:
        kind_id = int(parts[4])
        page = int(parts[5])
    except Exception:
        kind_id, page = 1, 0
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Техника: выберите:", reply_markup=admin_root_tech_items_kb(kind_id, page=page))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:item:"))
async def adm_root_tech_item(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    try:
        kind_id = int(parts[4])
        item_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    it = get_machine_item(item_id)
    mk = get_machine_kind(kind_id) or {}
    if not it:
        await c.answer("Не найдено", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"{(mk.get('title') or 'Техника')}: <b>{it['name']}</b>",
                        reply_markup=admin_root_tech_item_kb(kind_id, item_id))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:add:"))
async def adm_root_tech_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        kind_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        kind_id = 1
    mk = get_machine_kind(kind_id) or {"title": "Техника"}
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="tech_item", admin_kind_id=kind_id, admin_done=f"adm:root:tech:tractor")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите название техники ({mk['title']}):",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:tech:tractor")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:edit:"))
async def adm_root_tech_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    try:
        kind_id = int(parts[4])
        item_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    it = get_machine_item(item_id)
    if not it:
        await c.answer("Не найдено", show_alert=True)
        return
    await state.set_state(AdminFSM.edit_name)
    await state.update_data(edit_kind="tech_item", edit_id=item_id, edit_kind_id=kind_id)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите новое название техники:\n\nТекущее: <b>{it['name']}</b>",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm:root:tech:item:{kind_id}:{item_id}")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:del:"))
async def adm_root_tech_del(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    try:
        kind_id = int(parts[4])
        item_id = int(parts[5])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    it = get_machine_item(item_id)
    if not it:
        await c.answer("Не найдено", show_alert=True)
        return
    mk = get_machine_kind(kind_id) or {}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm:confirm:del:tech:{kind_id}:{item_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:root:tech:item:{kind_id}:{item_id}")]
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Точно удалить {(mk.get('title') or 'технику')}: <b>{it['name']}</b>?",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data == "adm:root:techkind:add")
async def adm_root_techkind_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="tech_kind", admin_done="adm:root:tech")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название нового типа техники (например: Комбайн):",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:tech")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data == "adm:root:techkind:del")
async def adm_root_techkind_del(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Удалить тип техники:", reply_markup=admin_root_tech_kind_del_kb(page=0))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:techkind:page:"))
async def adm_root_techkind_page(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        page = int(c.data.rsplit(":", 1)[1])
    except Exception:
        page = 0
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Удалить тип техники:", reply_markup=admin_root_tech_kind_del_kb(page=page))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:techkind:delpick:"))
async def adm_root_techkind_delpick(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        kind_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    mk = get_machine_kind(kind_id)
    if not mk:
        await c.answer("Не найдено", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm:confirm:del:techkind:{kind_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:root:tech")]
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Точно удалить тип техники <b>{mk['title']}</b>?\n\n"
                        f"Вместе с ним удалится список техники внутри.",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data == "adm:root:crop")
async def adm_root_crop(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культуры: выберите культуру:", reply_markup=admin_root_crop_list_kb(page=0))
    await c.answer()

# legacy handlers below are disabled (kept only for reference)
@router.callback_query(F.data.startswith("adm:root:tech:legacy:add:"))
async def adm_root_tech_add_legacy(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    sub = c.data.split(":")[4]
    label = "Трактор" if sub == "tractor" else "КамАЗ"
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="act", admin_grp="tech")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите название техники ({label}):",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:tech")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:legacy:del:"))
async def adm_root_tech_del_legacy(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    sub = c.data.split(":")[4]
    label = "Трактор" if sub == "tractor" else "КамАЗ"
    items = list_activities(GROUP_TECH)
    kb = InlineKeyboardBuilder()
    if items:
        for it in items:
            safe = it.replace(":", "_")[:20]
            kb.button(text=f"🗑 {it}", callback_data=f"adm:root:tech:delpick:{safe}")
        kb.adjust(2)
    else:
        kb.button(text="— список пуст —", callback_data="adm:root:tech")
    kb.button(text="🔙 Назад", callback_data="adm:root:tech")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Удалить технику ({label}):", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:legacy:delpick:"))
async def adm_root_tech_delpick_legacy(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    name = c.data.split(":", 3)[3].replace("_", " ")
    remove_activity(name)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Техника '{name}' удалена.", reply_markup=admin_root_tech_kb())
    await c.answer("Удалено")

@router.callback_query(F.data == "adm:root:crop:add")
async def adm_root_crop_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="crop", admin_grp="crop", admin_done="adm:root:crop")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название культуры:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:crop")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop:page:"))
async def adm_root_crop_page(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        page = int(c.data.rsplit(":", 1)[1])
    except Exception:
        page = 0
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культуры: выберите культуру:", reply_markup=admin_root_crop_list_kb(page=page))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop:item:"))
async def adm_root_crop_item(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        crop_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    crop = get_crop_by_rowid(crop_id)
    if not crop:
        await c.answer("Культура не найдена", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Культура: <b>{crop['name']}</b>", reply_markup=admin_root_crop_item_kb(crop_id))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop:edit:"))
async def adm_root_crop_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        crop_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    crop = get_crop_by_rowid(crop_id)
    if not crop:
        await c.answer("Культура не найдена", show_alert=True)
        return
    await state.set_state(AdminFSM.edit_name)
    await state.update_data(edit_kind="crop", edit_id=crop_id)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Введите новое название культуры:\n\nТекущее: <b>{crop['name']}</b>",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm:root:crop:item:{crop_id}")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop:delid:"))
async def adm_root_crop_delid(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        crop_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    crop = get_crop_by_rowid(crop_id)
    if not crop:
        await c.answer("Культура не найдена", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"adm:confirm:del:crop:{crop_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:root:crop:item:{crop_id}")]
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Точно удалить культуру <b>{crop['name']}</b>?",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data.startswith("adm:confirm:del:"))
async def adm_confirm_delete(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    # adm:confirm:del:<kind>:...
    kind = parts[3] if len(parts) > 3 else ""
    ok = False
    if kind == "loc" and len(parts) >= 5:
        ok = delete_location_by_id(int(parts[4]))
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Удалено" if ok else "⚠️ Не удалось удалить"),
                            reply_markup=admin_root_loc_list_kb(page=0))
    elif kind == "act" and len(parts) >= 6:
        grp = parts[4]
        ok = delete_activity_by_id(int(parts[5]))
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Удалено" if ok else "⚠️ Не удалось удалить"),
                            reply_markup=admin_root_act_list_kb(grp, page=0))
    elif kind == "crop" and len(parts) >= 5:
        ok = delete_crop_by_rowid(int(parts[4]))
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Удалено" if ok else "⚠️ Не удалось удалить"),
                            reply_markup=admin_root_crop_list_kb(page=0))
    elif kind == "tech" and len(parts) >= 6:
        kind_id = int(parts[4])
        ok = delete_machine_item(int(parts[5]))
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Удалено" if ok else "⚠️ Не удалось удалить"),
                            reply_markup=admin_root_tech_items_kb(kind_id, page=0))
    elif kind == "techkind" and len(parts) >= 5:
        ok = delete_machine_kind(int(parts[4]))
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Удалено" if ok else "⚠️ Не удалось удалить"),
                            reply_markup=admin_root_tech_kb())
    else:
        await c.answer("Некорректное подтверждение", show_alert=True)
        return
    await c.answer("Удалено" if ok else "Ошибка", show_alert=not ok)

@router.callback_query(F.data == "adm:roles")
async def adm_roles(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👥 Управление ролями:", reply_markup=admin_roles_kb())
    await c.answer()

@router.callback_query(F.data == "adm:role:add:brig")
async def adm_role_add_brig(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.add_brig_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Введите @username или выберите из списка:",
        reply_markup=admin_role_add_brig_kb(page=0),
    )
    await c.answer()

@router.message(AdminFSM.add_brig_id)
async def adm_role_add_brig_value(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    target_id = None
    try:
        target_id = int(raw)
    except ValueError:
        u = find_user_by_username(raw)
        if u:
            target_id = u["user_id"]
    if not target_id:
        await message.answer(
            "Введите @username или выберите из списка:",
            reply_markup=admin_role_add_brig_kb(page=0),
        )
        return
    set_role(target_id, "brigadier", message.from_user.id)
    tu = get_user(target_id) or {}
    add_brigadier(target_id, tu.get("username"), tu.get("full_name"), message.from_user.id)
    await state.clear()
    await message.answer(f"Роль бригадира выдана пользователю {target_id}",
                         reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:role:del:brig")
async def adm_role_del_brig(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.del_brig_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Выберите бригадира из списка или введите @username:",
        reply_markup=admin_role_del_brig_kb(page=0),
    )
    await c.answer()

@router.message(AdminFSM.del_brig_id)
async def adm_role_del_brig_value(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    target_id = None
    try:
        target_id = int(raw)
    except ValueError:
        u = find_user_by_username(raw)
        if u:
            target_id = u["user_id"]
    if not target_id:
        await message.answer(
            "Выберите бригадира из списка или введите @username:",
            reply_markup=admin_role_del_brig_kb(page=0),
        )
        return
    clear_role(target_id, "brigadier")
    remove_brigadier(target_id)
    await state.clear()
    await message.answer(f"Роль бригадира снята с пользователя {target_id}",
                         reply_markup=admin_menu_kb())

@router.callback_query(F.data.startswith("adm:role:add:brig:page:"))
async def adm_role_add_brig_page(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        page = int(c.data.rsplit(":", 1)[1])
    except Exception:
        page = 0
    await state.set_state(AdminFSM.add_brig_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Введите @username или выберите из списка:",
        reply_markup=admin_role_add_brig_kb(page=page),
    )
    await c.answer()

@router.callback_query(F.data.startswith("adm:role:del:brig:page:"))
async def adm_role_del_brig_page(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        page = int(c.data.rsplit(":", 1)[1])
    except Exception:
        page = 0
    await state.set_state(AdminFSM.del_brig_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        "Выберите бригадира из списка или введите @username:",
        reply_markup=admin_role_del_brig_kb(page=page),
    )
    await c.answer()

@router.callback_query(F.data.startswith("adm:role:add:brig:pick:"))
async def adm_role_add_brig_pick(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        target_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    set_role(target_id, "brigadier", c.from_user.id)
    tu = get_user(target_id) or {}
    add_brigadier(target_id, tu.get("username"), tu.get("full_name"), c.from_user.id)
    await state.clear()
    who = _display_user(tu.get("full_name"), tu.get("username"), target_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        f"✅ Роль бригадира выдана: <b>{who}</b>",
        reply_markup=admin_roles_kb(),
    )
    await c.answer("Готово")

@router.callback_query(F.data.startswith("adm:role:del:brig:pick:"))
async def adm_role_del_brig_pick(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    try:
        target_id = int(c.data.rsplit(":", 1)[1])
    except Exception:
        await c.answer("Некорректный выбор", show_alert=True)
        return
    clear_role(target_id, "brigadier")
    remove_brigadier(target_id)
    await state.clear()
    tu = get_user(target_id) or {}
    who = _display_user(tu.get("full_name"), tu.get("username"), target_id)
    await _edit_or_send(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        f"✅ Роль бригадира снята: <b>{who}</b>",
        reply_markup=admin_roles_kb(),
    )
    await c.answer("Готово")

# -------------- Изменение имени --------------

@router.callback_query(F.data == "menu:name")
async def cb_menu_name(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_settings_menu(c.bot, c.message.chat.id, c.from_user.id)
    await c.answer()

@router.callback_query(F.data == "menu:name:change")
async def cb_menu_name_change(c: CallbackQuery, state: FSMContext):
    await state.set_state(NameFSM.waiting_name)
    await state.update_data(name_change_from_settings=True)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "✏️ Введите <b>Фамилию Имя</b> для изменения (например: <b>Иванов Иван</b>):",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:name")]
                        ]))
    await c.answer()

@router.callback_query(F.data == "menu:phone")
async def cb_menu_phone(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await _prompt_phone_registration(c, state, back_cb="menu:name")
    await c.answer()

@router.message(PhoneFSM.waiting_phone_text)
async def capture_phone_text(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if raw.lower() in {"отмена", "cancel", "/cancel"}:
        await state.clear()
        await _ui_reset(message.bot, message.chat.id, message.from_user.id)
        return

    phone = normalize_phone(raw)
    if not phone:
        await message.answer(
            "❌ Не понял номер.\n\n"
            "Введите в любом формате: <b>+7XXXXXXXXXX</b>, <b>8XXXXXXXXXX</b> или <b>9XXXXXXXXX</b>.\n"
            "Пример: <code>+7 989 834 1458</code>",
        )
        return

    await state.update_data(pending_phone=phone)
    await state.set_state(PhoneFSM.waiting_phone_contact)
    await message.answer(
        f"Теперь подтвердите номер <b>{phone}</b>.\n"
        "Нажмите кнопку <b>«📱 Отправить контакт»</b> (она отправит ваш контакт с номером Telegram).",
        reply_markup=phone_contact_kb(),
    )

@router.message(PhoneFSM.waiting_phone_contact, F.contact)
async def capture_phone_contact(message: Message, state: FSMContext):
    contact = message.contact
    if not contact:
        return

    # request_contact отправляет контакт самого пользователя (user_id должен совпасть)
    if getattr(contact, "user_id", None) and int(contact.user_id) != int(message.from_user.id):
        await message.answer("❌ Нужно отправить <b>свой</b> контакт кнопкой «📱 Отправить контакт».")
        return

    phone_from_contact = normalize_phone(getattr(contact, "phone_number", "") or "")
    if not phone_from_contact:
        await message.answer("❌ Не смог прочитать номер из контакта. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    pending = (data.get("pending_phone") or "").strip()
    if pending and phone_from_contact != pending:
        await message.answer(
            "❌ Номер из контакта не совпал с введённым.\n\n"
            f"Введено: <b>{pending}</b>\n"
            f"В контакте: <b>{phone_from_contact}</b>\n\n"
            "Введите номер заново.",
            reply_markup=reply_menu_kb(),
        )
        await state.set_state(PhoneFSM.waiting_phone_text)
        return

    ok = set_user_phone(message.from_user.id, phone_from_contact)
    if not ok:
        await message.answer(
            "❌ Этот номер уже привязан к другому пользователю.\n"
            "Если это ошибка — напишите администратору.",
            reply_markup=reply_menu_kb(),
        )
        await state.set_state(PhoneFSM.waiting_phone_text)
        return

    await state.clear()
    await message.answer(f"✅ Телефон сохранён: <b>{phone_from_contact}</b>", reply_markup=reply_menu_kb())
    await _ui_reset(message.bot, message.chat.id, message.from_user.id)

# -------------- Статистика кнопки --------------

@router.callback_query(F.data == "stats:today")
async def cb_stats_today(c: CallbackQuery):
    await show_stats_today(c.message.chat.id, c.from_user.id, is_admin(c))
    await c.answer()

@router.callback_query(F.data == "stats:week")
async def cb_stats_week(c: CallbackQuery):
    await show_stats_week(c.message.chat.id, c.from_user.id, is_admin(c))
    await c.answer()

@router.callback_query(F.data == "stats:month")
async def cb_stats_month(c: CallbackQuery):
    # В меню периода кнопка "Месяц" должна работать так же, как "Сегодня/Неделя"
    await show_stats_period(c.message.chat.id, c.from_user.id, "month")
    await c.answer()

def _format_user_label(user_id: int, full_name: str = "", username: str = "") -> str:
    name = (full_name or "").strip()
    uname = (username or "").strip()
    if uname and not uname.startswith("@"):
        uname = "@" + uname
    if name and uname:
        return f"{name} {uname}"
    if name:
        return name
    if uname:
        return uname
    return str(user_id)

async def _admin_stats_show_user_list(bot: Bot, chat_id: int, actor_id: int, *, period: str, page: int, state: FSMContext) -> None:
    start, end = _stats_period_range(period)
    users = fetch_users_with_reports_range(start.isoformat(), end.isoformat())
    period_str = _stats_period_label(period, start, end)

    page_size = 10
    total = len(users)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    chunk = users[page * page_size : (page + 1) * page_size]

    kb = InlineKeyboardBuilder()
    if not chunk:
        kb.row(InlineKeyboardButton(text="— нет записей —", callback_data="menu:stats"))
    else:
        for uid, full_name, uname in chunk:
            label = _format_user_label(int(uid), full_name, uname)[:64]
            kb.row(InlineKeyboardButton(text=label, callback_data=f"adm:stats:edit:{period}:u:{int(uid)}:rp:0:lp:{page}"))

    nav = InlineKeyboardBuilder()
    if pages > 1:
        if page > 0:
            nav.button(text="⬅️", callback_data=f"adm:stats:edit:{period}:p:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="menu:stats")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:stats:edit:{period}:p:{page+1}")
        nav.adjust(3)
        kb.row(*nav.buttons)

    kb.row(InlineKeyboardButton(text="📊 К статистике", callback_data="menu:stats"))
    kb.row(InlineKeyboardButton(text="🧰 В меню", callback_data="menu:root"))

    # сохраняем контекст возврата (для edit flow)
    await state.update_data(
        edit_return_mode="adm_stats_user_list",
        edit_return_period=period,
        edit_return_list_page=page,
    )
    await _edit_or_send(
        bot,
        chat_id,
        actor_id,
        f"✏️ <b>Админ: изменение/удаление</b>\nВыберите сотрудника за {period_str}:",
        reply_markup=kb.as_markup(),
    )

async def _admin_stats_show_user_reports(
    bot: Bot,
    chat_id: int,
    actor_id: int,
    *,
    period: str,
    target_user_id: int,
    rpage: int,
    lpage: int,
    state: FSMContext,
) -> None:
    start, end = _stats_period_range(period)
    period_str = _stats_period_label(period, start, end)
    rows = fetch_reports_for_user_range(target_user_id, start.isoformat(), end.isoformat())

    page_size = 8
    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    rpage = max(0, min(int(rpage), pages - 1))
    chunk = rows[rpage * page_size : (rpage + 1) * page_size]

    # Заголовок
    u = get_user(target_user_id) or {}
    title_user = _format_user_label(target_user_id, u.get("full_name", ""), u.get("username", ""))
    text = [f"📝 <b>{html.escape(title_user)}</b>\nЗаписи за {period_str}:"]
    kb = InlineKeyboardBuilder()

    if not chunk:
        text.append("\n— нет записей —")
    else:
        for rid, d, act, loc, h, created, mtype, mname, crop, trips in chunk:
            extra = []
            if crop:
                extra.append(f"культура: {crop}")
            if mtype:
                extra.append(mtype if not mname else f"{mtype} {mname}")
            if trips:
                extra.append(f"рейсов: {trips}")
            extra_str = f" ({'; '.join(extra)})" if extra else ""
            text.append(f"\n• #{rid} {d} | {loc} — {act}: <b>{h}</b> ч{extra_str}")
            kb.row(
                InlineKeyboardButton(text=f"🖊 Изменить #{rid}", callback_data=f"edit:chg:{rid}:{d}"),
                InlineKeyboardButton(text=f"🗑 Удалить #{rid}", callback_data=f"edit:del:{rid}"),
            )

    # Навигация по страницам
    if pages > 1:
        nav = InlineKeyboardBuilder()
        if rpage > 0:
            nav.button(text="⬅️", callback_data=f"adm:stats:edit:{period}:u:{target_user_id}:rp:{rpage-1}:lp:{lpage}")
        nav.button(text=f"{rpage+1}/{pages}", callback_data="menu:stats")
        if rpage < pages - 1:
            nav.button(text="➡️", callback_data=f"adm:stats:edit:{period}:u:{target_user_id}:rp:{rpage+1}:lp:{lpage}")
        nav.adjust(3)
        kb.row(*nav.buttons)

    kb.row(InlineKeyboardButton(text="🔙 К списку сотрудников", callback_data=f"adm:stats:edit:{period}:p:{lpage}"))
    kb.row(InlineKeyboardButton(text="🧰 В меню", callback_data="menu:root"))

    # контекст возврата из EditFSM
    await state.update_data(
        edit_return_mode="adm_stats_user",
        edit_return_period=period,
        edit_return_uid=int(target_user_id),
        edit_return_rpage=int(rpage),
        edit_return_lpage=int(lpage),
        edit_return_cb=f"adm:stats:edit:{period}:u:{int(target_user_id)}:rp:{int(rpage)}:lp:{int(lpage)}",
    )
    await _edit_or_send(bot, chat_id, actor_id, "\n".join(text), reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm:stats:edit:"))
async def adm_stats_edit_router(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    # adm:stats:edit:{period}[:p:{page}]  OR  adm:stats:edit:{period}:u:{uid}:rp:{rpage}:lp:{lpage}
    period = parts[3] if len(parts) > 3 else "week"
    if len(parts) == 4:
        await _admin_stats_show_user_list(c.bot, c.message.chat.id, c.from_user.id, period=period, page=0, state=state)
        await c.answer()
        return
    # page list
    if len(parts) >= 6 and parts[4] == "p":
        page = int(parts[5])
        await _admin_stats_show_user_list(c.bot, c.message.chat.id, c.from_user.id, period=period, page=page, state=state)
        await c.answer()
        return
    # user reports
    if len(parts) >= 10 and parts[4] == "u":
        uid = int(parts[5])
        # parts[6] == rp, parts[8] == lp
        rpage = int(parts[7]) if len(parts) > 7 else 0
        lpage = int(parts[9]) if len(parts) > 9 else 0
        await _admin_stats_show_user_reports(
            c.bot,
            c.message.chat.id,
            c.from_user.id,
            period=period,
            target_user_id=uid,
            rpage=rpage,
            lpage=lpage,
            state=state,
        )
        await c.answer()
        return
    await c.answer("Некорректная команда", show_alert=True)

# Совместимость со старым callback из меню (если где-то осталось)
@router.callback_query(F.data.startswith("stats:adm:edit:"))
async def adm_stats_edit_compat(c: CallbackQuery, state: FSMContext):
    # stats:adm:edit:{period}
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    period = (c.data.split(":")[3] if len(c.data.split(":")) > 3 else "week")
    await _admin_stats_show_user_list(c.bot, c.message.chat.id, c.from_user.id, period=period, page=0, state=state)
    await c.answer()

# -------------- WORK flow и Назад --------------

@router.callback_query(F.data == "work:back:grp")
async def back_to_work_grp(c: CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    
    # Определяем права администратора для выбора правильной клавиатуры
    class Dummy: pass
    dummy = Dummy()
    dummy.from_user = Dummy()
    dummy.from_user.id = c.from_user.id
    dummy.from_user.username = (u or {}).get("username")
    admin = is_admin(dummy)
    
    await state.set_state(WorkFSM.pick_group)
    
    # Используем соответствующую клавиатуру в зависимости от прав
    keyboard = work_groups_kb() if admin else work_groups_kb_user()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>тип работы</b>:", reply_markup=keyboard)
    await c.answer()

@router.callback_query(F.data == "work:back:act")
async def back_to_work_act(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    grp = data.get("work", {}).get("grp", GROUP_TECH)
    kind = "tech" if grp == GROUP_TECH else "hand"
    await state.set_state(WorkFSM.pick_activity)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>вид работы</b>:", reply_markup=activities_kb(kind))
    await c.answer()

@router.callback_query(F.data == "work:back:locgrp")
async def back_to_locgrp(c: CallbackQuery, state: FSMContext):
    await state.set_state(WorkFSM.pick_loc_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>локацию</b>:", reply_markup=loc_groups_kb())
    await c.answer()

@router.callback_query(F.data == "work:back:loc")
async def back_to_loc(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lg = data.get("work", {}).get("loc_grp", GROUP_FIELDS)
    kind = "fields" if lg == GROUP_FIELDS else "ware"
    await state.set_state(WorkFSM.pick_location)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>место</b>:", reply_markup=locations_kb(kind))
    await c.answer()

@router.callback_query(F.data == "work:back:date")
async def back_to_date(c: CallbackQuery, state: FSMContext):
    await state.set_state(WorkFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>дату</b>:", reply_markup=days_keyboard())
    await c.answer()

@router.callback_query(F.data.startswith("work:grp:"))
async def pick_work_group(c: CallbackQuery, state: FSMContext):
    kind = c.data.split(":")[2]  # tech|hand
    grp_name = GROUP_TECH if kind=="tech" else GROUP_HAND
    data = await state.get_data()
    work = data.get("work", {})
    work["grp"] = grp_name
    await state.update_data(work=work)
    await state.set_state(WorkFSM.pick_activity)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>вид работы</b>:", reply_markup=activities_kb(kind))
    await c.answer()

@router.callback_query(F.data.startswith("work:act:"))
async def pick_activity(c: CallbackQuery, state: FSMContext):
    _, _, kind, name = c.data.split(":", 3)  # kind tech/hand
    grp_name = GROUP_TECH if kind=="tech" else GROUP_HAND
    if name == "__other__":
        await state.update_data(awaiting_custom_activity=grp_name)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите название работы (свободная форма):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="work:back:grp")]
                            ]))
    else:
        data = await state.get_data()
        work = data.get("work", {})
        work["grp"] = grp_name
        work["activity"] = name
        await state.update_data(work=work)
        await state.set_state(WorkFSM.pick_loc_group)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите <b>локацию</b>:", reply_markup=loc_groups_kb())
    await c.answer()

# Capture custom activity name only when not in Admin or Name states,
# so it doesn't swallow admin free-text additions.
@router.message(
    StateFilter(WorkFSM.pick_activity), 
    F.text & F.text.len() > 0
)
async def maybe_capture_custom_activity(message: Message, state: FSMContext):
    data = await state.get_data()
    grp_name = data.get("awaiting_custom_activity")
    if not grp_name:
        # Если не ждем кастомную активность, не обрабатываем
        return
    name = (message.text or "").strip()
    work = data.get("work", {})
    work["grp"] = grp_name
    work["activity"] = name
    await state.update_data(work=work, awaiting_custom_activity=None)
    await state.set_state(WorkFSM.pick_loc_group)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите <b>локацию</b>:", reply_markup=loc_groups_kb())

@router.callback_query(F.data.startswith("work:locgrp:"))
async def pick_loc_group(c: CallbackQuery, state: FSMContext):
    lg = c.data.split(":")[2]  # fields|ware
    grp = GROUP_FIELDS if lg=="fields" else GROUP_WARE
    data = await state.get_data()
    work = data.get("work", {})
    work["loc_grp"] = grp
    
    if lg == "ware":
        # Для склада сразу устанавливаем локацию "Склад" и переходим к дате
        work["location"] = "Склад"
        await state.update_data(work=work)
        await state.set_state(WorkFSM.pick_date)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите <b>дату</b>:", reply_markup=days_keyboard())
    else:
        # Для полей показываем список конкретных полей
        await state.update_data(work=work)
        await state.set_state(WorkFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите <b>место</b>:", reply_markup=locations_kb(lg))
    
    await c.answer()

@router.callback_query(F.data.startswith("work:loc:"))
async def pick_location(c: CallbackQuery, state: FSMContext):
    _, _, lg, loc = c.data.split(":", 3)
    grp = GROUP_FIELDS if lg=="fields" else GROUP_WARE
    data = await state.get_data()
    work = data.get("work", {})
    work["loc_grp"] = grp
    if loc == "__other__":
        await state.update_data(work=work, awaiting_custom_location=lg)
        await state.set_state(WorkFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите локацию (свободная форма):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"work:locgrp:{lg}")]
                            ]))
        await c.answer()
        return
    work["location"] = loc
    await state.update_data(work=work, awaiting_custom_location=None)
    await state.set_state(WorkFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>дату</b>:", reply_markup=days_keyboard())
    await c.answer()

@router.message(
    StateFilter(WorkFSM.pick_location),
    F.text & F.text.len() > 0
)
async def maybe_capture_custom_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lg = data.get("awaiting_custom_location")
    if not lg:
        return
    loc = (message.text or "").strip()
    if not loc:
        return
    grp = GROUP_FIELDS if lg=="fields" else GROUP_WARE
    work = data.get("work", {})
    work["loc_grp"] = grp
    work["location"] = loc
    await state.update_data(work=work, awaiting_custom_location=None)
    await state.set_state(WorkFSM.pick_date)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите <b>дату</b>:", reply_markup=days_keyboard())

@router.callback_query(F.data.startswith("work:date:"))
async def pick_date(c: CallbackQuery, state: FSMContext):
    d = c.data.split(":")[2]
    data = await state.get_data()
    work = data.get("work", {})
    work["work_date"] = d
    await state.update_data(work=work)
    await state.set_state(WorkFSM.pick_hours)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>кол-во часов</b>:", reply_markup=hours_keyboard())
    await c.answer()

@router.callback_query(F.data.startswith("work:hours:"))
async def pick_hours(c: CallbackQuery, state: FSMContext):
    hours = int(c.data.split(":")[2])
    data = await state.get_data()
    work = data.get("work", {})
    if not all(k in work for k in ("grp","activity","loc_grp","location","work_date")):
        await c.answer("Что-то пошло не так. Начните заново.", show_alert=True)
        await show_main_menu(c.message.chat.id, c.from_user.id, get_user(c.from_user.id), "Меню")
        return

    # проверка лимита 24 часа
    already = sum_hours_for_user_date(c.from_user.id, work["work_date"])
    if already + hours > 24:
        await c.answer("❗ В сутки нельзя больше 24 ч. Выберите меньшее число.", show_alert=True)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            f"На {work['work_date']} уже учтено {already} ч. Выберите другое количество:",
                            reply_markup=hours_keyboard())
        return

    # сохраняем
    u = get_user(c.from_user.id)
    rid = insert_report(
        user_id=c.from_user.id,
        reg_name=(u.get("full_name") or ""),
        username=(u.get("username") or ""),
        location=work["location"],
        loc_grp=work["loc_grp"],
        activity=work["activity"],
        act_grp=work["grp"],
        work_date=work["work_date"],
        hours=hours,
        chat_id=c.message.chat.id
    )
    # Публикация в топике статистики
    try:
        await stats_notify_created(c.bot, rid)
    except Exception:
        pass
    try:
        await request_export_soon(otd=True, brig=False, reason="otd:create")
    except Exception:
        pass
    text = (
        "✅ <b>Сохранено</b>\n\n"
        f"Дата: <b>{work['work_date']}</b>\n"
        f"Место: <b>{work['location']}</b>\n"
        f"Работа: <b>{work['activity']}</b>\n"
        f"Часы: <b>{hours}</b>\n"
        f"ID записи: <code>#{rid}</code>"
    )
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=_ui_back_to_root_kb())
    await c.answer()

# -------------- Перепись: удалить/изменить -------------

@router.callback_query(F.data.startswith("edit:del:"))
async def cb_edit_delete(c: CallbackQuery):
    rid = int(c.data.split(":")[2])
    before = get_report(rid)
    ok = delete_report(rid, c.from_user.id)
    if ok:
        await c.answer("Удалено")
    else:
        await c.answer("Не получилось удалить (возможно, запись не ваша или старше 24ч)", show_alert=True)
    # Обновим сводку в статистике (если была удалена)
    if ok:
        try:
            await stats_notify_deleted(c.bot, rid, deleted=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:delete")
        except Exception:
            pass
    await cb_menu_edit(c)

@router.callback_query(F.data.startswith("edit:chg:"))
async def cb_edit_change(c: CallbackQuery, state:FSMContext):
    _, _, rid, work_d = c.data.split(":", 3)
    rid = int(rid)
    report = get_report(rid) or {}
    fields_text = [
        f"1. Дата: <b>{report.get('work_date') or '—'}</b>",
        f"2. Часы: <b>{report.get('hours') or '—'}</b>",
        f"3. Локация: <b>{report.get('location') or '—'}</b>",
        f"4. Вид работы: <b>{report.get('activity') or '—'}</b>",
        f"5. Техника: <b>{(report.get('machine_type') or '—')} {(report.get('machine_name') or '')}</b>",
        f"6. Культура: <b>{report.get('crop') or '—'}</b>",
        f"7. Рейсы: <b>{report.get('trips') or 0}</b>",
    ]
    text = "📝 <b>Изменение записи #{}</b>\n\n{}\n\nВведите номера полей через запятую, которые хотите изменить (например: 1,4,7)".format(
        rid, "\n".join(fields_text)
    )
    await state.set_state(EditFSM.waiting_field_numbers)
    await state.update_data(edit_id=rid, edit_date=work_d, edit_queue_active=True, edit_queue=[], edit_current=None)
    await _send_new_message(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:edit")]
            ]
        )
    )
    await c.answer()

def _edit_back_cb(data: dict, rid:int, edit_date:str=""):
    if data.get("edit_queue_active"):
        return "edit:queue:back"
    return f"edit:chg:{rid}:{edit_date}"

def _edit_summary_text(report: dict) -> str:
    return (
        f"📅 Дата: <b>{report.get('work_date') or '—'}</b>\n"
        f"📍 Место: <b>{report.get('location') or '—'}</b>\n"
        f"🧰 Работа: <b>{report.get('activity') or '—'}</b>\n"
            f"🚜 Техника: <b>{report.get('machine_type') or '—'} {report.get('machine_name') or ''}</b>\n"
            f"🌱 Культура: <b>{report.get('crop') or '—'}</b>\n"
            f"🚚 Рейсы: <b>{report.get('trips') or 0}</b>\n"
        f"⏰ Часы: <b>{report.get('hours') or '—'}</b>"
    )

async def _start_next_edit_in_queue(bot: Bot, chat_id:int, user_id:int, state:FSMContext):
    data = await state.get_data()
    queue = data.get("edit_queue") or []
    rid = data.get("edit_id")
    edit_date = data.get("edit_date", "")
    if not queue:
        report = get_report(rid) or {}
        text = f"✅ Обновление завершено.\n\n{_edit_summary_text(report)}"
        await state.clear()
        await _send_new_message(
            bot,
            chat_id,
            user_id,
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:edit")]
                ]
            )
        )
        return
    field = queue[0]
    await state.update_data(edit_current=field, edit_queue=queue[1:], edit_queue_active=True)
    back_cb = "edit:queue:back"
    if field == "date":
        await state.set_state(EditFSM.waiting_new_date)
        await bot.send_message(
            chat_id,
            "Введите дату в формате ГГГГ-ММ-ДД или ДД.ММ.ГГ:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]]
            ),
        )
    elif field == "hours":
        await state.set_state(EditFSM.waiting_new_hours)
        kb = InlineKeyboardBuilder()
        for h in range(1, 25):
            kb.button(text=str(h), callback_data=f"edit:h:{h}")
        kb.adjust(6)
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb))
        await bot.send_message(
            chat_id,
            f"Укажите <b>новое количество часов</b> для записи #{rid}:",
            reply_markup=kb.as_markup()
        )
    elif field == "loc":
        await state.set_state(EditFSM.waiting_new_location)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Поля", callback_data=f"edit:locgrp:fields:{rid}")],
            [InlineKeyboardButton(text="Склад", callback_data=f"edit:locgrp:ware:{rid}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)],
        ])
        await bot.send_message(
            chat_id,
            f"Выберите <b>группу локаций</b> для записи #{rid}:",
            reply_markup=kb
        )
    elif field == "act":
        await state.set_state(EditFSM.waiting_new_activity)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Техника", callback_data=f"edit:actgrp:tech:{rid}")],
            [InlineKeyboardButton(text="Ручная", callback_data=f"edit:actgrp:hand:{rid}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)],
        ])
        await bot.send_message(
            chat_id,
            f"Выберите <b>группу работ</b> для записи #{rid}:",
            reply_markup=kb
        )
    elif field == "machine":
        await state.set_state(EditFSM.waiting_new_machine)
        await bot.send_message(
            chat_id,
            "Введите новую технику (например: «Трактор JD8» или «КамАЗ»):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]]
            )
        )
    elif field == "crop":
        await state.set_state(EditFSM.waiting_new_crop)
        await bot.send_message(
            chat_id,
            "Введите культуру (например: Подсолнечник):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]]
            )
        )
    elif field == "trips":
        await state.set_state(EditFSM.waiting_new_trips)
        await bot.send_message(
            chat_id,
            "Введите количество рейсов (целое число):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)]]
            )
        )

@router.callback_query(F.data == "edit:queue:back")
async def edit_queue_back(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await c.answer()
        return
    report = get_report(rid) or {}
    fields_text = [
        f"1. Дата: <b>{report.get('work_date') or '—'}</b>",
        f"2. Часы: <b>{report.get('hours') or '—'}</b>",
        f"3. Локация: <b>{report.get('location') or '—'}</b>",
        f"4. Вид работы: <b>{report.get('activity') or '—'}</b>",
        f"5. Техника: <b>{(report.get('machine_type') or '—')} {(report.get('machine_name') or '')}</b>",
        f"6. Культура: <b>{report.get('crop') or '—'}</b>",
        f"7. Рейсы: <b>{report.get('trips') or 0}</b>",
    ]
    text = "📝 <b>Изменение записи #{}</b>\n\n{}\n\nВведите номера полей через запятую, которые хотите изменить (например: 1,4,7)".format(
        rid, "\n".join(fields_text)
    )
    await state.set_state(EditFSM.waiting_field_numbers)
    await state.update_data(edit_queue_active=True, edit_queue=[], edit_current=None)
    await _send_new_message(
        c.bot,
        c.message.chat.id,
        c.from_user.id,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:edit")]
            ]
        )
    )
    await c.answer()

def _edit_queue_from_input(text: str) -> List[str]:
    mapping = {
        1: "date",
        2: "hours",
        3: "loc",
        4: "act",
        5: "machine",
        6: "crop",
        7: "trips",
    }
    result = []
    parts = text.replace(" ", "").split(",")
    for p in parts:
        if not p:
            continue
        try:
            num = int(p)
        except ValueError:
            return []
        if num not in mapping:
            return []
        if mapping[num] not in result:
            result.append(mapping[num])
    return result

@router.message(EditFSM.waiting_field_numbers)
async def edit_pick_fields(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    queue = _edit_queue_from_input(text)
    data = await state.get_data()
    rid = data.get("edit_id")
    if not queue or not rid:
        await message.answer(
            "Введите номера полей через запятую, например: 1,4,7",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:edit")]
                ]
            )
        )
        return
    await state.update_data(edit_queue=queue, edit_queue_active=True, edit_current=None)
    await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)

# Обработчик выбора типа изменения
@router.callback_query(F.data.startswith("edit:type:"))
async def cb_edit_type(c: CallbackQuery, state: FSMContext):
    print(f"[DEBUG] cb_edit_type called with data: {c.data}")
    _, _, edit_type, rid = c.data.split(":", 3)
    rid = int(rid)
    print(f"[DEBUG] edit_type: {edit_type}, rid: {rid}")
    
    if edit_type == "hours":
        # Изменение времени - показываем сетку часов
        await state.set_state(EditFSM.waiting_new_hours)
        await state.update_data(edit_id=rid)
        
        kb = InlineKeyboardBuilder()
        for h in range(1, 25):
            kb.button(text=str(h), callback_data=f"edit:h:{h}")
        kb.adjust(6)  # 6 столбцов
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        back_cb = _edit_back_cb(data, rid, edit_date)
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb))
        
        await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                            f"Укажите <b>новое количество часов</b> для записи #{rid}:",
                            reply_markup=kb.as_markup())
    
    elif edit_type == "loc":
        # Изменение локации - показываем группы локаций
        await state.set_state(EditFSM.waiting_new_location)
        await state.update_data(edit_id=rid)
        
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Поля", callback_data=f"edit:locgrp:fields:{rid}")],
            [InlineKeyboardButton(text="Склад", callback_data=f"edit:locgrp:ware:{rid}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))],
        ])
        
        await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                            f"Выберите <b>группу локаций</b> для записи #{rid}:",
                            reply_markup=kb)
    
    elif edit_type == "act":
        # Изменение вида работы - показываем группы работ
        await state.set_state(EditFSM.waiting_new_activity)
        await state.update_data(edit_id=rid)
        
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Техника", callback_data=f"edit:actgrp:tech:{rid}")],
            [InlineKeyboardButton(text="Ручная", callback_data=f"edit:actgrp:hand:{rid}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))],
        ])
        
        await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                            f"Выберите <b>группу работ</b> для записи #{rid}:",
                            reply_markup=kb)
    elif edit_type == "machine":
        await state.set_state(EditFSM.waiting_new_machine)
        await state.update_data(edit_id=rid)
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        await _send_new_message(
            c.bot,
            c.message.chat.id,
            c.from_user.id,
            "Введите новую технику (например: «Трактор JD8» или «КамАЗ»):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))]
                ]
            )
        )

    elif edit_type == "crop":
        await state.set_state(EditFSM.waiting_new_crop)
        await state.update_data(edit_id=rid)
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        await _send_new_message(
            c.bot, c.message.chat.id, c.from_user.id,
            "Введите культуру (например: Подсолнечник):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))]]
            )
        )

    elif edit_type == "date":
        await state.set_state(EditFSM.waiting_new_date)
        await state.update_data(edit_id=rid)
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        await _send_new_message(
            c.bot, c.message.chat.id, c.from_user.id,
            "Введите дату в формате ГГГГ-ММ-ДД или ДД.ММ.ГГ:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))]]
            )
        )

    elif edit_type == "trips":
        await state.set_state(EditFSM.waiting_new_trips)
        await state.update_data(edit_id=rid)
        data = await state.get_data()
        edit_date = data.get('edit_date', '')
        await _send_new_message(
            c.bot, c.message.chat.id, c.from_user.id,
            "Введите количество рейсов (целое число):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, edit_date))]]
            )
        )
    
    await c.answer()

@router.callback_query(F.data.startswith("edit:h:"))
async def cb_edit_hours_value(c: CallbackQuery, state: FSMContext):
    new_h = int(c.data.split(":")[2])
    data = await state.get_data()
    rid = data.get("edit_id")
    work_d = data.get("edit_date")
    
    if rid is None or work_d is None:
        await c.answer("Ошибка: данные не найдены. Начните заново.", show_alert=True)
        await cb_menu_edit(c)
        return
    
    rid = int(rid)
    before = get_report(rid)
    # лимит 24
    already = sum_hours_for_user_date(c.from_user.id, work_d, exclude_report_id=rid)
    if already + new_h > 24:
        await c.answer("❗ В сутки нельзя больше 24 ч. Выберите меньшее число.", show_alert=True)
        return
    ok = update_report_hours(rid, c.from_user.id, new_h)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(c.bot, rid, before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        await c.answer("Обновлено")
        if queue_active:
            await _start_next_edit_in_queue(c.bot, c.message.chat.id, c.from_user.id, state)
        else:
            await cb_menu_edit(c)
    else:
        await c.answer("Не получилось обновить", show_alert=True)

# Обработчики для изменения локации
@router.callback_query(F.data.startswith("edit:locgrp:"))
async def cb_edit_location_group(c: CallbackQuery, state: FSMContext):
    _, _, grp, rid = c.data.split(":", 3)
    rid = int(rid)
    
    # Показываем список локаций в выбранной группе
    if grp == "fields":
        locations = list_locations(GROUP_FIELDS)
        grp_name = "Поля"
    else:
        locations = list_locations(GROUP_WARE)
        grp_name = "Склад"
    
    kb = InlineKeyboardBuilder()
    for loc in locations:
        kb.button(text=loc, callback_data=f"edit:loc:{grp}:{loc}:{rid}")
    kb.adjust(2)
    data = await state.get_data()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, data.get("edit_date", ""))))
    
    await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                        f"Выберите <b>локацию</b> в группе {grp_name}:",
                        reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("edit:loc:"))
async def cb_edit_location_final(c: CallbackQuery, state: FSMContext):
    _, _, grp, loc, rid = c.data.split(":", 4)
    rid = int(rid)
    before = get_report(rid)
    
    # Обновляем локацию
    grp_name = GROUP_FIELDS if grp == "fields" else GROUP_WARE
    ok = update_report_location(rid, c.from_user.id, loc, grp_name)
    
    if ok:
        data = await state.get_data()
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(c.bot, rid, before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        await c.answer("Локация обновлена")
        if queue_active:
            await _start_next_edit_in_queue(c.bot, c.message.chat.id, c.from_user.id, state)
        else:
            await cb_menu_edit(c)
    else:
        await c.answer("Не получилось обновить локацию", show_alert=True)

# Обработчики для изменения вида работы
@router.callback_query(F.data.startswith("edit:actgrp:"))
async def cb_edit_activity_group(c: CallbackQuery, state: FSMContext):
    _, _, grp, rid = c.data.split(":", 3)
    rid = int(rid)
    
    # Показываем список активностей в выбранной группе
    if grp == "tech":
        activities = list_activities(GROUP_TECH)
        grp_name = "Техника"
    else:
        activities = list_activities(GROUP_HAND)
        grp_name = "Ручная"
    
    kb = InlineKeyboardBuilder()
    for act in activities:
        kb.button(text=act, callback_data=f"edit:act:{grp}:{act}:{rid}")
    kb.button(text="Прочее…", callback_data=f"edit:act:{grp}:__other__:{rid}")
    kb.adjust(2)
    data = await state.get_data()
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data=_edit_back_cb(data, rid, data.get("edit_date", ""))))
    
    await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                        f"Выберите <b>вид работы</b> в группе {grp_name}:",
                        reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("edit:act:"))
async def cb_edit_activity_final(c: CallbackQuery, state: FSMContext):
    _, _, grp, act, rid = c.data.split(":", 4)
    rid = int(rid)
    
    if act == "__other__":
        # Пользователь выбрал "Прочее" - ждем ввод текста
        await state.set_state(EditFSM.waiting_new_activity)
        await state.update_data(edit_id=rid, edit_grp=grp)
        
        await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите название работы (свободная форма):",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit:actgrp:{grp}:{rid}")]
                            ]))
    else:
        before = get_report(rid)
        # Обновляем активность
        grp_name = GROUP_TECH if grp == "tech" else GROUP_HAND
        ok = update_report_activity(rid, c.from_user.id, act, grp_name)
        
        if ok:
            data = await state.get_data()
            queue_active = data.get("edit_queue_active")
            if queue_active:
                await state.update_data(edit_queue_active=True)
            else:
                await state.clear()
            try:
                await stats_notify_changed(c.bot, rid, before=before)
            except Exception:
                pass
            try:
                await request_export_soon(otd=True, brig=False, reason="otd:update")
            except Exception:
                pass
            await c.answer("Вид работы обновлен")
            if queue_active:
                await _start_next_edit_in_queue(c.bot, c.message.chat.id, c.from_user.id, state)
            else:
                await cb_menu_edit(c)
        else:
            await c.answer("Не получилось обновить вид работы", show_alert=True)
    
    await c.answer()

# Обработчик ввода кастомной активности
@router.message(EditFSM.waiting_new_activity)
async def cb_edit_custom_activity(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    data = await state.get_data()
    rid = data.get("edit_id")
    grp = data.get("edit_grp")
    
    if not rid or not grp:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Ошибка: данные не найдены. Начните заново.")
        return
    
    act_name = (message.text or "").strip()
    if not act_name:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Введите название работы.")
        return
    
    # Обновляем активность
    grp_name = GROUP_TECH if grp == "tech" else GROUP_HAND
    before = get_report(int(rid))
    ok = update_report_activity(rid, message.from_user.id, act_name, grp_name)
    
    if ok:
        queue_active = (await state.get_data()).get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(message.bot, int(rid), before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Не получилось обновить вид работы")

@router.message(EditFSM.waiting_new_machine)
async def cb_edit_machine(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Ошибка: данные не найдены. Начните заново.")
        return
    text = (message.text or "").strip()
    if not text:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Введите технику, например: Трактор JD8")
        return
    parts = text.split()
    machine_type = parts[0]
    machine_name = " ".join(parts[1:]) if len(parts) > 1 else None
    before = get_report(int(rid))
    ok = update_report_machine(int(rid), message.from_user.id, machine_type, machine_name)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(message.bot, int(rid), before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Не получилось обновить технику")

@router.message(EditFSM.waiting_new_crop)
async def cb_edit_crop(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Ошибка: данные не найдены. Начните заново.")
        return
    crop = (message.text or "").strip()
    if not crop:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Введите название культуры.")
        return
    before = get_report(int(rid))
    ok = update_report_crop(int(rid), message.from_user.id, crop)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(message.bot, int(rid), before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Не получилось обновить культуру")

@router.message(EditFSM.waiting_new_trips)
async def cb_edit_trips(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Ошибка: данные не найдены. Начните заново.")
        return
    try:
        trips = int((message.text or "").strip())
    except ValueError:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Введите количество рейсов числом.")
        return
    before = get_report(int(rid))
    ok = update_report_trips(int(rid), message.from_user.id, trips)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(message.bot, int(rid), before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Не получилось обновить рейсы")

@router.message(EditFSM.waiting_new_date)
async def cb_edit_date(message: Message, state: FSMContext):
    await _ui_try_delete_user_message(message)
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Ошибка: данные не найдены. Начните заново.")
        return
    raw = (message.text or "").strip()
    new_date = None
    try:
        new_date = date.fromisoformat(raw).isoformat()
    except Exception:
        try:
            new_date = datetime.strptime(raw, "%d.%m.%y").date().isoformat()
        except Exception:
            pass
    if not new_date:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Неверный формат даты. Используйте ГГГГ-ММ-ДД или ДД.ММ.ГГ.")
        return
    before = get_report(int(rid))
    ok = update_report_date(int(rid), message.from_user.id, new_date)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(message.bot, int(rid), before=before)
        except Exception:
            pass
        try:
            await request_export_soon(otd=True, brig=False, reason="otd:update")
        except Exception:
            pass
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Не получилось обновить дату")

async def cb_menu_edit_from_message(message: Message):
    """Вспомогательная функция для возврата к меню редактирования из текстового сообщения"""
    rows = user_recent_24h_reports(message.from_user.id)
    if not rows:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "📝 За последние 48 часов записей нет.")
        return
    
    kb = InlineKeyboardBuilder()
    text = ["📝 <b>Ваши записи за последние 48 часов</b>:"]
    for rid, d, act, loc, h, created, mtype, mname, crop, trips in rows:
        extra = []
        if crop:
            extra.append(f"культура: {crop}")
        if mtype:
            extra.append(mtype if not mname else f"{mtype} {mname}")
        if trips:
            extra.append(f"рейсов: {trips}")
        extra_str = f" ({'; '.join(extra)})" if extra else ""
        text.append(f"• #{rid} {d} | {loc} — {act}: <b>{h}</b> ч{extra_str}")
        kb.row(
            InlineKeyboardButton(text=f"🖊 Изменить #{rid}", callback_data=f"edit:chg:{rid}:{d}"),
            InlineKeyboardButton(text=f"🗑 Удалить #{rid}", callback_data=f"edit:del:{rid}")
        )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "\n".join(text), reply_markup=kb.as_markup())

# -------------- Админ: добавить/удалить --------------

@router.callback_query(F.data == "adm:add:act")
async def adm_add_act(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.add_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу работ:", reply_markup=admin_pick_group_kb("act"))
    await c.answer()

@router.callback_query(F.data == "adm:add:loc")
async def adm_add_loc(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.add_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу локаций:", reply_markup=admin_pick_group_kb("loc"))
    await c.answer()

# выбор группы (ADD) — работает ТОЛЬКО когда мы в состоянии add_group
@router.callback_query(AdminFSM.add_group, F.data.startswith("adm:grp:"))
async def adm_pick_group(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    _, _, kind, grp = c.data.split(":")
    await state.update_data(admin_kind=kind, admin_grp=grp)
    await state.set_state(AdminFSM.add_name)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название для добавления:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:admin")]
                        ]))
    await c.answer()

@router.message(AdminFSM.add_name)
async def adm_add_name_value(message: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("admin_kind")
    grp = data.get("admin_grp")
    done = data.get("admin_done") or "menu:admin"
    kind_id = data.get("admin_kind_id")
    name = (message.text or "").strip()
    ok = False
    if kind == "act":
        ok = add_activity(GROUP_TECH if grp=="tech" else GROUP_HAND, name)
    elif kind == "crop":
        ok = add_crop(name)
    elif kind == "tech_kind":
        ok = add_machine_kind(name, mode="list")
    elif kind == "tech_item":
        try:
            ok = add_machine_item(int(kind_id), name) if kind_id is not None else False
        except Exception:
            ok = False
    else:
        ok = add_location(GROUP_FIELDS if grp=="fields" else GROUP_WARE, name)
    await state.clear()
    text = (f"✅ Добавлено: <b>{name}</b>" if ok else f"⚠️ Не получилось (возможно, уже есть): <b>{name}</b>")
    # Возврат туда, откуда пришли (root-списки / админ-меню)
    if done == "adm:root:loc":
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_root_loc_list_kb(page=0))
        return
    if done.startswith("adm:root:act:grp:"):
        grp2 = done.rsplit(":", 1)[1]
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_root_act_list_kb(grp2, page=0))
        return
    if done == "adm:root:crop":
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_root_crop_list_kb(page=0))
        return
    if done == "adm:root:tech":
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_root_tech_kb())
        return
    if done == "adm:root:tech:tractor":
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_root_tech_items_kb(1, page=0))
        return
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=admin_menu_kb())

@router.message(AdminFSM.edit_name)
async def adm_edit_name_value(message: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("edit_kind")
    edit_id = data.get("edit_id")
    grp = data.get("edit_grp")
    kind_id = data.get("edit_kind_id")
    new_name = (message.text or "").strip()
    if not new_name:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id, "Название не может быть пустым. Введите снова.")
        return

    # Подтверждение изменения (без применения сразу)
    await state.set_state(AdminFSM.edit_confirm)
    await state.update_data(pending_new_name=new_name)

    old_name = "—"
    cancel_cb = "menu:admin"
    if kind == "loc" and edit_id:
        loc = get_location_by_id(int(edit_id))
        old_name = (loc or {}).get("name") or "—"
        cancel_cb = f"adm:root:loc:item:{int(edit_id)}"
    elif kind == "act" and edit_id:
        act = get_activity_by_id(int(edit_id))
        old_name = (act or {}).get("name") or "—"
        cancel_cb = f"adm:root:act:item:{grp}:{int(edit_id)}"
    elif kind == "crop" and edit_id:
        crop = get_crop_by_rowid(int(edit_id))
        old_name = (crop or {}).get("name") or "—"
        cancel_cb = f"adm:root:crop:item:{int(edit_id)}"
    elif kind == "tech_item" and edit_id:
        it = get_machine_item(int(edit_id))
        old_name = (it or {}).get("name") or "—"
        cancel_cb = f"adm:root:tech:item:{int(kind_id) if kind_id else 1}:{int(edit_id)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="adm:confirm:edit")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_cb)]
    ])
    await _edit_or_send(
        message.bot,
        message.chat.id,
        message.from_user.id,
        f"Подтвердить изменение?\n\n<b>{old_name}</b> → <b>{new_name}</b>",
        reply_markup=kb,
    )

@router.callback_query(AdminFSM.edit_confirm, F.data == "adm:confirm:edit")
async def adm_confirm_edit(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    data = await state.get_data()
    kind = data.get("edit_kind")
    edit_id = data.get("edit_id")
    grp = data.get("edit_grp")
    kind_id = data.get("edit_kind_id")
    new_name = (data.get("pending_new_name") or "").strip()
    ok = False
    if kind == "loc":
        ok = update_location_name(int(edit_id), new_name) if edit_id else False
        await state.clear()
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Изменено" if ok else "⚠️ Не удалось изменить"),
                            reply_markup=admin_root_loc_list_kb(page=0))
    elif kind == "act":
        ok = update_activity_name(int(edit_id), new_name) if edit_id else False
        await state.clear()
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Изменено" if ok else "⚠️ Не удалось изменить"),
                            reply_markup=admin_root_act_list_kb(grp or "tech", page=0))
    elif kind == "crop":
        ok = update_crop_name(int(edit_id), new_name) if edit_id else False
        await state.clear()
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Изменено" if ok else "⚠️ Не удалось изменить"),
                            reply_markup=admin_root_crop_list_kb(page=0))
    elif kind == "tech_item":
        ok = update_machine_item(int(edit_id), new_name) if edit_id else False
        await state.clear()
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            ("✅ Изменено" if ok else "⚠️ Не удалось изменить"),
                            reply_markup=admin_root_tech_items_kb(int(kind_id) if kind_id else 1, page=0))
    else:
        await state.clear()
        await c.answer("Ошибка состояния", show_alert=True)
        return
    await c.answer("Готово" if ok else "Ошибка", show_alert=not ok)

@router.callback_query(F.data == "adm:del:act")
async def adm_del_act(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.del_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу работ для удаления:",
                        reply_markup=admin_pick_group_kb("act"))
    await c.answer()

@router.callback_query(F.data == "adm:del:loc")
async def adm_del_loc(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.del_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу локаций для удаления:",
                        reply_markup=admin_pick_group_kb("loc"))
    await c.answer()

# Кнопка «Назад» внутри списков удаления
@router.callback_query(F.data == "adm:grp:act")
async def adm_back_del_act(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.del_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу работ для удаления:",
                        reply_markup=admin_pick_group_kb("act"))
    await c.answer()

@router.callback_query(F.data == "adm:grp:loc")
async def adm_back_del_loc(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminFSM.del_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите группу локаций для удаления:",
                        reply_markup=admin_pick_group_kb("loc"))
    await c.answer()

# выбор группы (DEL) — эти обработчики сработают ТОЛЬКО когда мы в состоянии del_group
@router.callback_query(AdminFSM.del_group, F.data.startswith("adm:grp:act:"))
async def adm_del_act_group(c: CallbackQuery, state: FSMContext):
    grp = c.data.split(":")[3]  # tech/hand
    await state.update_data(del_kind="act", del_grp=grp)
    await state.set_state(AdminFSM.del_pick)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите работу для удаления:", reply_markup=admin_delete_list_kb("act", grp))
    await c.answer()

@router.callback_query(AdminFSM.del_group, F.data.startswith("adm:grp:loc:"))
async def adm_del_loc_group(c: CallbackQuery, state: FSMContext):
    grp = c.data.split(":")[3]  # fields/ware
    await state.update_data(del_kind="loc", del_grp=grp)
    await state.set_state(AdminFSM.del_pick)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите локацию для удаления:", reply_markup=admin_delete_list_kb("loc", grp))
    await c.answer()

@router.callback_query(AdminFSM.del_pick, F.data.startswith("adm:delpick:"))
async def adm_delete_pick(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True); return
    _, _, kind, grp, safe_name = c.data.split(":", 4)
    
    # Получаем оригинальные имена для поиска
    if kind == "act":
        items = list_activities(GROUP_TECH if grp=="tech" else GROUP_HAND)
    else:
        items = list_locations(GROUP_FIELDS if grp=="fields" else GROUP_WARE)
    
    # Ищем оригинальное имя по безопасной версии
    original_name = None
    for item in items:
        safe_item = item.replace(":", "_").replace(" ", "_")[:20]
        if safe_item == safe_name:
            original_name = item
            break
    
    if not original_name:
        await c.answer("Не удалось найти элемент для удаления", show_alert=True)
        return
    
    # Удаляем элемент
    ok = remove_activity(original_name) if kind == "act" else remove_location(original_name)
    if ok:
        await c.answer("Удалено")
    else:
        await c.answer("Не удалось удалить", show_alert=True)
    
    # Перерисуем список
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Обновлён список. Ещё удалить?",
                        reply_markup=admin_delete_list_kb(kind, grp))

# -------------- Админ: экспорт в Google Sheets --------------

@router.callback_query(F.data == "adm:export")
async def adm_export(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    
    await c.answer("Начинаю экспорт...")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "⏳ Экспортирую отчеты в Google Sheets...",
                        reply_markup=None)
    
    # Выполняем экспорт в отдельном потоке, чтобы не блокировать бота
    try:
        async with _export_lock:
            count1, msg1 = await asyncio.to_thread(export_reports_to_sheets)
            count2, msg2 = await asyncio.to_thread(export_brigadier_reports_to_sheets)
        
        parts = []
        if count1 > 0:
            parts.append("✅ " + msg1)
        else:
            parts.append("ℹ️ " + msg1)
        if count2 > 0:
            parts.append("✅ " + msg2)
        else:
            parts.append("ℹ️ " + msg2)
        text = "\n".join(parts)
        
        # Проверяем и создаем таблицу для следующего месяца
        created, sheet_msg = await asyncio.to_thread(check_and_create_next_month_sheet)
        if created:
            text += f"\n\n📅 {sheet_msg}"
        
    except Exception as e:
        logging.error(f"Export error in handler: {e}")
        text = f"❌ Ошибка экспорта: {str(e)}"
    
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text,
                        reply_markup=admin_menu_kb())

# -------------- Фолбэк на текст вне ожиданий --------------

@router.message(StateFilter(None), F.text)
async def any_text(message: Message):
    # В запрещённых темах/чате не реагируем (чтобы в группе были только отчёты)
    if not _is_allowed_topic(message):
        return
    u = get_user(message.from_user.id)
    await show_main_menu(message.chat.id, message.from_user.id, u, "Меню")

# -----------------------------
# main() и запуск (v3 Dispatcher/Router)
# -----------------------------

bot: Bot
dp: Dispatcher
scheduler: Optional[AsyncIOScheduler] = None

# -----------------------------
# Export-on-change (debounced)
# -----------------------------
_export_lock = asyncio.Lock()
_export_task: Optional[asyncio.Task] = None
_export_last_request_ts: float = 0.0
_export_pending = {"otd": False, "brig": False}


async def request_export_soon(*, otd: bool = True, brig: bool = True, reason: str = "") -> None:
    """
    Дебаунсим экспорт в Google Sheets при изменениях в БД:
    - любое количество изменений за короткий промежуток объединяем в 1 экспорт
    - выполняем экспорт в отдельном потоке (to_thread), чтобы не блокировать polling
    """
    global _export_task, _export_last_request_ts

    if not EXPORT_ON_CHANGE_ENABLED:
        return

    loop = asyncio.get_running_loop()
    _export_last_request_ts = loop.time()
    if otd:
        _export_pending["otd"] = True
    if brig:
        _export_pending["brig"] = True

    # если воркер ещё не запущен — запускаем
    if _export_task is None or _export_task.done():
        _export_task = asyncio.create_task(_export_worker(), name="export_on_change")

    if reason:
        logging.info(f"[export-on-change] requested ({reason})")


async def _export_worker() -> None:
    global _export_task
    loop = asyncio.get_running_loop()
    debounce = max(1, int(EXPORT_ON_CHANGE_DEBOUNCE_SEC))

    while True:
        await asyncio.sleep(debounce)
        if loop.time() - _export_last_request_ts < debounce:
            # за время сна пришли новые изменения — подождём ещё
            continue

        do_otd = bool(_export_pending.get("otd"))
        do_brig = bool(_export_pending.get("brig"))
        _export_pending["otd"] = False
        _export_pending["brig"] = False

        if not do_otd and not do_brig:
            break

        try:
            async with _export_lock:
                if do_otd:
                    await asyncio.to_thread(export_reports_to_sheets)
                    await asyncio.to_thread(check_and_create_next_month_sheet)
                if do_brig:
                    await asyncio.to_thread(export_brigadier_reports_to_sheets)
        except Exception as e:
            logging.error(f"[export-on-change] export failed: {e}")

        # если за время экспорта не пришли новые изменения — выходим
        if loop.time() - _export_last_request_ts >= debounce and not _export_pending["otd"] and not _export_pending["brig"]:
            break

    _export_task = None

async def scheduled_export():
    """Задача для автоматического экспорта"""
    try:
        logging.info("Running scheduled export...")
        async with _export_lock:
            c1, m1 = await asyncio.to_thread(export_reports_to_sheets)
            c2, m2 = await asyncio.to_thread(export_brigadier_reports_to_sheets)
        logging.info(f"Scheduled export OTD: {m1}")
        logging.info(f"Scheduled export BRIG: {m2}")
        
        # Проверяем создание таблицы для следующего месяца
        created, sheet_msg = await asyncio.to_thread(check_and_create_next_month_sheet)
        if created:
            logging.info(sheet_msg)
            
    except Exception as e:
        logging.error(f"Scheduled export error: {e}")

async def main():
    global bot, dp, scheduler
    init_db()

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router_topics)  # Роутер модерации тем (должен быть первым)
    dp.include_router(router)

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Запуск"),
            BotCommand(command="today", description="Статистика за сегодня"),
            BotCommand(command="my", description="Моя статистика (неделя)"),
            BotCommand(command="menu", description="Открыть меню бота"),
            BotCommand(command="phone", description="Указать/изменить номер телефона"),
            BotCommand(command="where", description="Показать chat_id и thread_id"),
            BotCommand(command="version", description="Версия бота (диагностика)"),
            BotCommand(command="init_hours", description="Инициализировать тему Часы (админ)"),
        ])
    except Exception:
        pass

    # Настройка автоматического экспорта
    if AUTO_EXPORT_ENABLED:
        scheduler = AsyncIOScheduler()
        
        # Парсим cron выражение
        cron_parts = AUTO_EXPORT_CRON.split()
        if len(cron_parts) == 5:
            minute, hour, day, month, day_of_week = cron_parts
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )
            scheduler.add_job(scheduled_export, trigger)
            scheduler.start()
            logging.info(f"Scheduled export enabled: {AUTO_EXPORT_CRON}")
        else:
            logging.warning(f"Invalid cron expression: {AUTO_EXPORT_CRON}")

    print("[main] db initialized")
    await ensure_robot_banner(bot)

    # Read-only чат: запрещаем писать обычным пользователям на уровне прав чата
    # (админы всё равно смогут писать). Если нет прав у бота — просто игнорируем.
    if READONLY_CHAT_ID is not None:
        # Проверим права бота в чате, чтобы было понятно почему не удаляет/не ограничивает.
        try:
            me = await bot.me()
            cm = await bot.get_chat_member(READONLY_CHAT_ID, me.id)
            is_admin_here = isinstance(cm, (ChatMemberAdministrator, ChatMemberOwner))
            can_delete = bool(getattr(cm, "can_delete_messages", False))
            can_restrict = bool(getattr(cm, "can_restrict_members", False))
            logging.info(
                f"[readonly] chat={READONLY_CHAT_ID} bot_is_admin={is_admin_here} "
                f"can_delete_messages={can_delete} can_restrict_members={can_restrict}"
            )
        except Exception as e:
            logging.warning(f"[readonly] cannot inspect bot permissions in chat {READONLY_CHAT_ID}: {e}")

        try:
            await bot.set_chat_permissions(
                chat_id=READONLY_CHAT_ID,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_other_messages=False,
                    can_send_polls=False,
                    can_add_web_page_previews=False,
                    can_invite_users=False,
                    can_change_info=False,
                    can_pin_messages=False,
                ),
            )
        except TelegramForbiddenError as e:
            logging.warning(f"[readonly] cannot set chat permissions in chat {READONLY_CHAT_ID}: {e}")
        except TelegramBadRequest as e:
            logging.info(f"[readonly] set_chat_permissions bad request in chat {READONLY_CHAT_ID}: {e}")
        except Exception as e:
            logging.warning(f"[readonly] set_chat_permissions failed in chat {READONLY_CHAT_ID}: {e}")
    
    try:
        # Не ограничиваем allowed_updates: иначе можно случайно отрезать callback_query,
        # и тогда inline-кнопки "не работают" (команды при этом продолжают работать).
        await dp.start_polling(bot)
    finally:
        if scheduler:
            scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
    



















