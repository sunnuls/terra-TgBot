# bot_polya.py
# -*- coding: utf-8 -*-

import asyncio
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

def _runtime_version_info(user_id: int, username: Optional[str]) -> str:
    repo_dir = Path(__file__).resolve().parent
    sha = os.getenv("GIT_SHA", "").strip() or _read_git_short_sha(repo_dir) or "unknown"
    try:
        mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        mtime = "unknown"
    role = get_role_label(user_id)
    uname = (username or "").lstrip("@")
    return (
        f"version: <code>{sha}</code>\n"
        f"started: <code>{STARTED_AT.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"file_mtime: <code>{mtime}</code>\n"
        f"role: <code>{role}</code>\n"
        f"user: <code>{user_id}</code> @{uname if uname else '-'}</code>"
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

DB_PATH = os.path.join(os.getcwd(), "reports.db")

# Google Sheets настройки
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]
OAUTH_CLIENT_JSON = os.getenv("OAUTH_CLIENT_JSON", "oauth_client.json")
TOKEN_JSON_PATH = Path(os.getenv("TOKEN_JSON_PATH", "token.json"))
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
EXPORT_PREFIX = os.getenv("EXPORT_PREFIX", "WorkLog")

# Расписание автоматического экспорта (каждую неделю в понедельник в 9:00)
AUTO_EXPORT_ENABLED = os.getenv("AUTO_EXPORT_ENABLED", "false").lower() == "true"
AUTO_EXPORT_CRON = os.getenv("AUTO_EXPORT_CRON", "0 9 * * 1")  # каждый понедельник в 9:00

# Настройки чатов/топиков (форумов) из .env
# - WORK_CHAT_ID: id супергруппы, где идёт «работа»
# - WORK_TOPIC_ID: id топика с иконкой робота, где показываем меню/диалоги
# - STATS_CHAT_ID: id супергруппы для публикации статистики (может совпадать с WORK_CHAT_ID)
# - STATS_TOPIC_ID: id отдельного топика, куда публикуются сводки
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

# -----------------------------
# Константы (дефолтные справочники)
# -----------------------------

DEFAULT_FIELDS = [
    "Северное","Фазенда","5 га","58 га","Фермерское","Сад",
    "Чеки №1","Чеки №2","Чеки №3","Рогачи (б)","Рогачи(М)",
    "Владимирова Аренда","МТФ",
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
    "58 га",
    "Аренда Третьяк (40 га)",
    "МТФ",
    "Рогачи (б)",
    "Рогачи(М)",
    "Северное",
    "Фазенда",
    "Фермерское",
    "Чеки Куропятника",
    "Аренда Третьяк",
    "Прочее",
]
OTD_CROPS = [
    "Кабачок",
    "Картошка",
    "Подсолнечник",
    "Кукуруза",
    "Пшеница",
    "Горох",
    "Прочее",
]
OTD_HAND_WORKS = [
    "Лесополоса",
    "Прополка",
    "Сев",
    "Уборка",
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
        if "tz" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN tz TEXT")

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
        r = c.execute("SELECT user_id, full_name, username, tz, created_at FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not r:
            return None
        return {
            "user_id": r[0],
            "full_name": r[1],
            "username": r[2],
            "tz": r[3] or TZ,
            "created_at": r[4],
        }

def find_user_by_username(username: str) -> Optional[dict]:
    uname = (username or "").lower().lstrip("@")
    if not uname:
        return None
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute("SELECT user_id, full_name, username, tz, created_at FROM users WHERE LOWER(username)=?", (uname,)).fetchone()
        if not r:
            return None
        return {
            "user_id": r[0],
            "full_name": r[1],
            "username": r[2],
            "tz": r[3] or TZ,
            "created_at": r[4],
        }

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
    rows: int,
    bags: int,
    workers: int,
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
    stats = {
        "zucchini_rows": 0,
        "zucchini_workers": 0,
        "potato_rows": 0,
        "potato_bags": 0,
        "potato_workers": 0,
        "details": [],
    }
    for w_type, w_rows, w_bags, w_workers, w_date in rows:
        d_str = date.fromisoformat(w_date).strftime("%d.%m")
        if w_type.lower().startswith("кабач"):
            stats["zucchini_rows"] += w_rows or 0
            stats["zucchini_workers"] += w_workers or 0
            stats["details"].append(f"{d_str} 🥒: {w_rows}р, {w_workers}чел")
        elif w_type.lower().startswith("карт"):
            stats["potato_rows"] += w_rows or 0
            stats["potato_bags"] += w_bags or 0
            stats["potato_workers"] += w_workers or 0
            stats["details"].append(f"{d_str} 🥔: {w_rows}р, {w_bags}с, {w_workers}чел")
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
        # Проверяем, существует ли отчет
        report = c.execute("SELECT id FROM reports WHERE id=? AND user_id=?", (report_id, user_id)).fetchone()
        if not report:
            return False
        
        # Удаляем отчет
        cur = c.execute("DELETE FROM reports WHERE id=? AND user_id=?", (report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_hours(report_id:int, user_id:int, new_hours:int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("UPDATE reports SET hours=? WHERE id=? AND user_id=?", (new_hours, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_location(report_id:int, user_id:int, new_location:str, new_location_grp:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("UPDATE reports SET location=?, location_grp=? WHERE id=? AND user_id=?", 
                       (new_location, new_location_grp, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_activity(report_id:int, user_id:int, new_activity:str, new_activity_grp:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("UPDATE reports SET activity=?, activity_grp=? WHERE id=? AND user_id=?", 
                       (new_activity, new_activity_grp, report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_machine(report_id:int, user_id:int, machine_type:Optional[str], machine_name:Optional[str]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute(
            "UPDATE reports SET machine_type=?, machine_name=? WHERE id=? AND user_id=?",
            (machine_type, machine_name, report_id, user_id)
        )
        con.commit()
        return cur.rowcount > 0

def update_report_crop(report_id:int, user_id:int, crop:Optional[str]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute(
            "UPDATE reports SET crop=? WHERE id=? AND user_id=?",
            (crop, report_id, user_id)
        )
        con.commit()
        return cur.rowcount > 0

def update_report_trips(report_id:int, user_id:int, trips:Optional[int]) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute(
            "UPDATE reports SET trips=? WHERE id=? AND user_id=?",
            (trips, report_id, user_id)
        )
        con.commit()
        return cur.rowcount > 0

def update_report_date(report_id:int, user_id:int, new_date:str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute(
            "UPDATE reports SET work_date=? WHERE id=? AND user_id=?",
            (new_date, report_id, user_id)
        )
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
            
            # Название таблицы с месяцем, годом и датой последнего обновления
            month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
            today = datetime.now().strftime("%d.%m.%Y")
            sheet_name = f"{month_names[month]} {year} ({today})"
            
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
            
            # Добавляем заголовки с повторными попытками
            headers = [["Дата", "Фамилия Имя", "Место работы", "Вид работы", "Количество часов"]]
            
            def update_headers():
                return sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range="A1:E1",
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
        except Exception as e:
            logging.error(f"Error creating sheet: {e}")
            return None, None

def get_reports_to_export():
    """Получить список отчетов для экспорта (новые, измененные, удаленные)"""
    with connect() as con, closing(con.cursor()) as c:
        # Получаем все отчеты, которые нужно экспортировать
        rows = c.execute("""
        SELECT r.id, r.work_date, r.reg_name, r.location, r.activity, r.hours, r.created_at,
               ge.report_id as is_exported, ge.row_number, ge.last_updated
        FROM reports r
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
            report_id, work_date, name, location, activity, hours, created_at, is_exported, row_number, last_updated = row
            d = datetime.fromisoformat(work_date)
            key = (d.year, d.month)
            if key not in reports_by_month:
                reports_by_month[key] = []
            reports_by_month[key].append((report_id, work_date, name, location, activity, hours, created_at, is_exported, row_number, last_updated))
        
        total_exported = 0
        total_updated = 0
        total_deleted = 0
        
        # Обрабатываем удаленные записи
        for report_id, spreadsheet_id, row_number in deleted_reports:
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
                today = datetime.now().strftime("%d.%m.%Y")
                new_name = f"{month_names[month]} {year} ({today})"
                
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
                    range="A:E"
                ).execute()
            
            try:
                result = retry_google_api_call(get_existing_data)
                existing_values = result.get("values", []) if result else []
                next_row = len(existing_values) + 1
            except Exception:
                next_row = 2  # Начинаем со второй строки (после заголовков)
            
            # Обрабатываем отчеты
            for report_id, work_date, name, location, activity, hours, created_at, is_exported, row_number, last_updated in reports:
                values = [work_date, name, location, activity, hours]
                
                if is_exported and row_number:
                    # Обновляем существующую запись с повторными попытками
                    def update_record():
                        return sheets_service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"A{row_number}:E{row_number}",
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
                            range=f"A{next_row}:E{next_row}",
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
    pick_activity = State()
    pick_location = State()
    pick_crop = State()
    pick_trips = State()
    confirm = State()

class AdminFSM(StatesGroup):
    add_group = State()
    add_name = State()
    del_group = State()
    del_pick = State()
    add_brig_id = State()
    del_brig_id = State()

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

# где хранить последнее сообщение (chat_id, user_id) -> message_id
last_message: Dict[Tuple[int, int], int] = {}

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
    target_chat_id, extra = _ui_route_kwargs(chat_id)
    key = (target_chat_id, user_id)
    mid = last_message.get(key)
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=target_chat_id,
                message_id=mid,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return
        except TelegramBadRequest as e:
            # Если содержимое не изменилось — не создаём новое сообщение
            if "message is not modified" in str(e).lower():
                return
            # Если сообщение не найдено или не может быть отредактировано — удаляем из кэша и создаем новое
            if "message to edit not found" in str(e).lower() or "message is not modified" in str(e).lower():
                del last_message[key]
            # Иначе попробуем отправить новое ниже
            pass
    # Если нет прошлого сообщения — отправим в нужное место (учтём подтему)
    m = await bot.send_message(target_chat_id, text, reply_markup=reply_markup, **extra)
    last_message[key] = m.message_id

async def _send_new_message(bot: Bot, chat_id: int, user_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup]=None):
    """Отправляет новое сообщение, удаляя предыдущее"""
    target_chat_id, extra = _ui_route_kwargs(chat_id)
    key = (target_chat_id, user_id)
    mid = last_message.get(key)
    
    print(f"[DEBUG] _send_new_message: key={key}, old_mid={mid}")
    
    # Отправляем новое сообщение
    m = await bot.send_message(target_chat_id, text, reply_markup=reply_markup, **extra)
    last_message[key] = m.message_id
    
    print(f"[DEBUG] _send_new_message: new_mid={m.message_id}")
    
    # Удаляем предыдущее сообщение если оно есть (после отправки нового)
    if mid and mid != m.message_id:
        try:
            print(f"[DEBUG] _send_new_message: deleting old message {mid}")
            await bot.delete_message(target_chat_id, mid)
            print(f"[DEBUG] _send_new_message: successfully deleted {mid}")
        except TelegramBadRequest as e:
            print(f"[DEBUG] _send_new_message: failed to delete {mid}: {e}")
            pass  # Игнорируем ошибки удаления

def reply_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🧰 Меню")]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )

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
    who = _format_user({"full_name": r.get("reg_name"), "username": r.get("username"), "user_id": r.get("user_id")})
    return (
        f"👤 <b>{who}</b>\n"
        f"📅 {r['work_date']}\n"
        f"📍 {r['location']}\n"
        f"🧰 {r['activity']}\n"
        f"⏱️ {r['hours']} ч\n"
        f"ID: <code>#{r['id']}</code>"
    )

async def stats_notify_created(bot: Bot, report_id:int):
    r = get_report(report_id)
    if not r:
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

async def stats_notify_changed(bot: Bot, report_id:int):
    r = get_report(report_id)
    if not r:
        return
    prev = stat_get_msg(report_id)
    chat_id, thread_id = await _stats_target()
    text = "✏️ Изменена запись\n\n" + _format_report_line(r)
    if prev:
        p_chat, _, p_msg, _ = prev
        try:
            await bot.edit_message_text(chat_id=p_chat, message_id=p_msg, text=text)
            stat_save_msg(report_id, p_chat, thread_id or 0, p_msg, "changed")
            return
        except TelegramBadRequest:
            pass
    # если не получилось — публикуем новую
    if chat_id:
        if thread_id:
            m = await bot.send_message(chat_id, text, message_thread_id=thread_id)
        else:
            m = await bot.send_message(chat_id, text)
        stat_save_msg(report_id, chat_id, thread_id or 0, m.message_id, "changed")

async def stats_notify_deleted(bot: Bot, report_id:int):
    prev = stat_get_msg(report_id)
    if prev:
        p_chat, _, p_msg, _ = prev
        try:
            await bot.edit_message_text(chat_id=p_chat, message_id=p_msg, text=f"🗑 Удалена запись\n\nID: <code>#{report_id}</code>")
            stat_save_msg(report_id, p_chat, prev[1] or 0, p_msg, "deleted")
            return
        except TelegramBadRequest:
            pass
    # нет предыдущего поста — отправим отдельным сообщением
    chat_id, thread_id = await _stats_target()
    if not chat_id:
        return
    text = f"🗑 Удалена запись\n\nID: <code>#{report_id}</code>"
    if thread_id:
        await bot.send_message(chat_id, text, message_thread_id=thread_id)
    else:
        await bot.send_message(chat_id, text)

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
        kb.button(text="Статистика", callback_data="brig:stats")
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
    kb.button(text="Трактор", callback_data="otd:mkind:tractor")
    kb.button(text="КамАЗ", callback_data="otd:mkind:kamaz")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:type"))
    return kb.as_markup()

def otd_tractor_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for name in OTD_TRACTORS:
        kb.button(text=name, callback_data=f"otd:tractor:{name}")
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
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="otd:back:fieldprev"))
    return kb.as_markup()

def otd_crops_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c_name in OTD_CROPS:
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
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить", callback_data="adm:add:loc")
    kb.button(text="➖ Удалить", callback_data="adm:del:loc")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_root_act_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить", callback_data="adm:add:act")
    kb.button(text="➖ Удалить", callback_data="adm:del:act")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_root_tech_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Трактор", callback_data="adm:root:tech:tractor")
    kb.button(text="КамАЗ", callback_data="adm:root:tech:kamaz")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_root_tech_actions_kb(sub: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить", callback_data=f"adm:root:tech:add:{sub}")
    kb.button(text="➖ Удалить", callback_data=f"adm:root:tech:del:{sub}")
    kb.button(text="🔙 Назад", callback_data="adm:root:tech")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    kb.adjust(2,1,1)
    return kb.as_markup()

def admin_root_crop_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить", callback_data="adm:root:crop:add")
    kb.button(text="➖ Удалить", callback_data="adm:root:crop:del")
    kb.button(text="🔙 Назад", callback_data="adm:root")
    kb.adjust(2,1)
    return kb.as_markup()

def admin_roles_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Выдать бригадира", callback_data="adm:role:add:brig")
    kb.button(text="➖ Снять бригадира", callback_data="adm:role:del:brig")
    kb.button(text="🔙 Назад", callback_data="menu:admin")
    kb.adjust(2,1)
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

# -------------- Команды --------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    init_db()
    u = get_user(message.from_user.id)
    if not u:
        upsert_user(message.from_user.id, None, TZ, message.from_user.username or "")
        u = get_user(message.from_user.id)
    
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await message.answer(
            "👋 Для начала введите <b>Фамилию Имя</b> (например: <b>Иванов Иван</b>).",
            reply_markup=reply_menu_kb()
        )
        return
    
    await message.answer("Добро пожаловать! Нажмите «🧰 Меню» внизу для действий.", reply_markup=reply_menu_kb())
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

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    # Проверяем разрешенную тему для команд
    if not _is_allowed_topic(message):
        return
    u = get_user(message.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await message.answer("Введите <b>Фамилию Имя</b> для регистрации (например: <b>Иванов Иван</b>).")
        return
    
    # Стараемся удалить команду пользователя, чтобы не плодить мусор
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    
    # Показываем inline меню
    name = u.get("full_name")
    role = get_role_label(message.from_user.id)
    role_suffix = " (бригадир)" if role == "brigadier" else (" (админ)" if role == "admin" else "")
    text = f"👋 Привет, <b>{name}</b>{role_suffix}!\n\nВыберите действие:"
    await message.answer(text, reply_markup=main_menu_kb(role))
    
    # Устанавливаем постоянную клавиатуру
    # Убираем отправку сообщения "Меню открыто" - оно не нужно

@router.message(Command("it"))
async def cmd_it_menu(message: Message):
    if not _is_allowed_topic(message):
        return
    if not (is_it(message.from_user.id, message.from_user.username) or is_admin(message)):
        await message.answer("Нет прав")
        return
    u = get_user(message.from_user.id)
    name = (u or {}).get("full_name") or "—"
    text = f"👋 Привет, <b>{name}</b> (IT)!\n\nВыберите действие:"
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=main_menu_kb("it"))

@router.message(Command("brig"))
async def cmd_brig_menu(message: Message):
    if not _is_allowed_topic(message):
        return
    if not (is_brigadier(message.from_user.id, message.from_user.username) or is_admin(message)):
        await message.answer("Нет прав")
        return
    u = get_user(message.from_user.id)
    name = (u or {}).get("full_name") or "—"
    text = f"👋 Привет, <b>{name}</b> (бригадир)!\n\nВыберите действие:"
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id, text, reply_markup=main_menu_kb("brigadier"))

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

@router.message(F.text == "🧰 Меню")
async def msg_persistent_menu(message: Message, state: FSMContext):
    u = get_user(message.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await message.answer("Введите <b>Фамилию Имя</b> для регистрации (например: <b>Иванов Иван</b>).")
        return

    # Удаляем текстовое сообщение пользователя "Меню"
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    
    # Показываем inline меню
    name = u.get("full_name")
    role = get_role_label(message.from_user.id)
    role_suffix = " (бригадир)" if role == "brigadier" else (" (админ)" if role == "admin" else "")
    text = f"👋 Привет, <b>{name}</b>{role_suffix}!\n\nВыберите действие:"
    await message.answer(text, reply_markup=main_menu_kb(role))
    
    # Устанавливаем постоянную клавиатуру
    # Убираем отправку сообщения "Меню открыто" - оно не нужно

# Удалены лишние обработчики кнопок постоянной клавиатуры

# -------------- Регистрация --------------

@router.message(NameFSM.waiting_name)
async def capture_full_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    from_settings = data.get("name_change_from_settings")
    back_cb = "menu:name" if from_settings else "menu:root"
    if len(text) < 3 or " " not in text:
        await message.answer(
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
    
    if is_new_user:
        # Первоначальная регистрация
        await message.answer("Отлично! Внизу у вас закреплена кнопка «🧰 Меню».", reply_markup=reply_menu_kb())
        await show_main_menu(message.chat.id, message.from_user.id, u, f"✅ Зарегистрировано как: <b>{text}</b>")
    else:
        # Изменение имени
        if from_settings:
            await show_settings_menu(message.bot, message.chat.id, message.from_user.id,
                                     f"✏️ Имя изменено на: <b>{text}</b>\n\nЗдесь вы можете сменить ФИО.")
        else:
            await show_main_menu(message.chat.id, message.from_user.id, u, f"✏️ Имя изменено на: <b>{text}</b>")

# -------------- Рисовалки экранов --------------

async def show_main_menu(chat_id:int, user_id:int, u:dict, header:str):
    class Dummy: pass
    dummy = Dummy()
    dummy.from_user = Dummy()
    dummy.from_user.id = user_id
    dummy.from_user.username = (u or {}).get("username")
    role = get_role_label(user_id)

    # у обычных статистика — без ФИО, а шапка остаётся
    name = (u or {}).get("full_name") or "—"
    role_suffix = " (бригадир)" if role == "brigadier" else (" (админ)" if role == "admin" else "")
    text = f"👋 Привет, <b>{name}</b>{role_suffix}!\n\nВыберите действие:"
    if role == "it":
        text += (
            "\n\nДоступные команды:\n"
            "• admin — админ-меню\n"
            "• brig — меню бригадиров\n"
            "• it — IT-меню\n"
            "• menu — основное меню"
        )
    if role == "admin":
        text += (
            "\n\nДоступные команды:\n"
            "• admin — админ-меню\n"
            "• brig — меню бригадиров\n"
            "• it — IT-меню\n"
            "• menu — основное меню"
        )
    
    # Отправляем сообщение с постоянной клавиатурой
    target_chat_id, extra = _ui_route_kwargs(chat_id)
    await bot.send_message(
        target_chat_id, 
        text, 
        reply_markup=main_menu_kb(role),
        **extra
    )
    
    # Отправляем отдельное сообщение с постоянной клавиатурой для обеспечения совместимости
    # Убираем отправку сообщения "Меню открыто" - оно не нужно

async def show_settings_menu(bot: Bot, chat_id:int, user_id:int, header:str="Здесь вы можете сменить ФИО."):
    await _edit_or_send(bot, chat_id, user_id, header, reply_markup=settings_menu_kb())

async def show_stats_today(chat_id:int, user_id:int, admin:bool, via_command=False):
    role = get_role_label(user_id)
    admin = role == "admin"
    if admin:
        rows = fetch_stats_today_all()
        if not rows:
            text = "📊 Сегодня записей нет."
        else:
            parts = ["📊 <b>Сегодня (все)</b>:"]
            cur_uid = None
            subtotal = 0
            for uid, full_name, uname, loc, act, h in rows:
                if uid != cur_uid:
                    if cur_uid is not None:
                        parts.append(f"  — Итого сотрудник: <b>{subtotal}</b> ч\n")
                    cur_uid = uid
                    subtotal = 0
                    who = full_name or (uname and "@"+uname) or str(uid)
                    parts.append(f"\n👤 <b>{who}</b>")
                parts.append(f"  • {loc} — {act}: <b>{h}</b> ч")
                subtotal += h
            if cur_uid is not None:
                parts.append(f"  — Итого сотрудник: <b>{subtotal}</b> ч")
            text = "\n".join(parts)
    else:
        today = date.today().isoformat()
        rows = fetch_stats_range_for_user(user_id, today, today)
        if not rows:
            text = "📊 Сегодня у вас записей нет."
        else:
            parts = ["📊 <b>Сегодня</b>:"]
            total = 0
            for d, loc, act, h in rows:
                parts.append(f"• {loc} — {act}: <b>{h}</b> ч")
                total += h
            parts.append(f"\nИтого: <b>{total}</b> ч")
            text = "\n".join(parts)
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=main_menu_kb(role))

async def show_stats_week(chat_id:int, user_id:int, admin:bool, via_command=False):
    role = get_role_label(user_id)
    admin = role == "admin"
    end = date.today()
    start = end - timedelta(days=6)
    if admin:
        rows = fetch_stats_range_all(start.isoformat(), end.isoformat())
        if not rows:
            text = "📊 За 7 дней записей нет."
        else:
            parts = [f"📊 <b>Неделя</b> ({start.strftime('%d.%m')}–{end.strftime('%d.%m')}):"]
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
            text = "\n".join(parts)
    else:
        rows = fetch_stats_range_for_user(user_id, start.isoformat(), end.isoformat())
        if not rows:
            text = "📊 За 7 дней у вас записей нет."
        else:
            parts = [f"📊 <b>Неделя</b> ({start.strftime('%d.%m')}–{end.strftime('%d.%m')}):"]
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
            text = "\n".join(parts)
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=main_menu_kb(role))

# -------------- Меню --------------

def _format_otd_summary(work: dict) -> str:
    lines = ["📋 <b>Проверьте данные</b>", ""]
    lines.append(f"1. Дата - {work.get('work_date', '—')}")
    lines.append(f"2. Часы - {work.get('hours', '—')}")
    machine_type = work.get("machine_type") or ("Ручная" if work.get("act_grp") == GROUP_HAND else "—")
    lines.append(f"3. {machine_type}")
    machine_name = work.get("machine_name") or "—"
    lines.append(f"4. {machine_name}")
    lines.append(f"5. Работа - {work.get('activity', '—')}")
    lines.append(f"6. Культура - {work.get('crop', '—')}")
    location = work.get("location") or "—"
    lines.append(f"7. Место - {location}")
    if work.get("machine_type") == "КамАЗ":
        lines.append(f"8. Рейсов - {work.get('trips') or 0}")
    lines.append("\nВсе верно?")
    return "\n".join(lines)

@router.callback_query(F.data == "menu:root")
async def cb_menu_root(c: CallbackQuery, state: FSMContext):
    await state.clear()  # очень важно: выходим из любого состояния
    await c.answer()  # закрыть «часики»
    
    u = get_user(c.from_user.id)
    
    # Генерируем текст и клавиатуру главного меню
    class Dummy: pass
    dummy = Dummy()
    dummy.from_user = Dummy()
    dummy.from_user.id = c.from_user.id
    dummy.from_user.username = (u or {}).get("username")
    role = get_role_label(c.from_user.id)
    
    name = (u or {}).get("full_name") or "—"
    role_suffix = " (бригадир)" if role == "brigadier" else (" (админ)" if role == "admin" else "")
    text = f"👋 Привет, <b>{name}</b>{role_suffix}!\n\nВыберите действие:"
    
    # Создаем новое сообщение, удаляя предыдущее
    await _send_new_message(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=main_menu_kb(role))

# Обработчик кнопки Start удален - теперь обычные пользователи сразу видят полное меню

@router.callback_query(F.data == "menu:work")
async def cb_menu_work(c: CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите <b>Фамилию Имя</b> для регистрации.")
        await c.answer()
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
    if role in ("admin", "brigadier", "it", "tim"):
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите период статистики:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="Сегодня", callback_data="stats:today")],
                                [InlineKeyboardButton(text="Неделя", callback_data="stats:week")],
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")],
                            ]))
    else:
        rows = fetch_stats_month_for_user(c.from_user.id)
        if not rows:
            text = "📊 За этот месяц у вас нет записей."
        else:
            text_parts = ["📊 <b>Отчеты за месяц</b>:"]
            for rid, d, act, loc, h, mtype, mname, crop, trips in rows:
                mt = mtype or ""
                mn = mname or ""
                extra = f" ({mt} {mn})".strip()
                crop_part = f" | {crop}" if crop else ""
                trips_part = f" | рейсов: {trips}" if trips else ""
                text_parts.append(f"• #{rid} {d} | {loc}{crop_part}{trips_part} — {act}{extra}: <b>{h}</b> ч")
            text = "\n".join(text_parts)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить / удалить", callback_data="menu:edit")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")],
        ])
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=kb)
    await c.answer()

# ---------------- ОТД (новый поток для работяг) ----------------

async def _otd_require_user(message_or_cb, state: FSMContext) -> Optional[dict]:
    u = get_user(message_or_cb.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(
            message_or_cb.bot,
            message_or_cb.message.chat.id if isinstance(message_or_cb, CallbackQuery) else message_or_cb.chat.id,
            message_or_cb.from_user.id,
            "Введите <b>Фамилию Имя</b> для регистрации."
        )
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.answer()
        return None
    return u

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
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите трактор:", reply_markup=otd_tractor_kb())
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
    if work.get("machine_type") == "КамАЗ" and work.get("trips") is not None:
        await state.set_state(OtdFSM.pick_location)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Где погружались?", reply_markup=otd_fields_kb("otd:load"))
    elif work.get("machine_type") == "Трактор":
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

async def _otd_set_hours(bot: Bot, chat_id: int, user_id: int, state: FSMContext, hours: int):
    if hours < 1 or hours > 24:
        await _edit_or_send(bot, chat_id, user_id, "Часы должны быть от 1 до 24. Введите снова:",
                            reply_markup=otd_hours_keyboard())
        return
    data = await state.get_data()
    work = data.get("otd", {})
    work["hours"] = hours
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_type)
    await _edit_or_send(bot, chat_id, user_id,
                        "Выберите тип работы:", reply_markup=otd_type_keyboard())

@router.callback_query(F.data.startswith("otd:hours:"))
async def otd_pick_hours_cb(c: CallbackQuery, state: FSMContext):
    hours = int(c.data.split(":", 2)[2])
    await _otd_set_hours(c.bot, c.message.chat.id, c.from_user.id, state, hours)
    await c.answer()

@router.message(OtdFSM.pick_hours)
async def otd_pick_hours_msg(message: Message, state: FSMContext):
    try:
        hours = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число часов (1-24) или нажмите кнопку.")
        return
    await _otd_set_hours(message.bot, message.chat.id, message.from_user.id, state, hours)

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
    mkind = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    if mkind == "tractor":
        work["machine_type"] = "Трактор"
        work["machine_name"] = None
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_machine)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите трактор:", reply_markup=otd_tractor_kb())
    else:
        work["machine_type"] = "КамАЗ"
        work["machine_name"] = "КамАЗ"
        await state.update_data(otd=work)
        await state.set_state(OtdFSM.pick_crop)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Культура:", reply_markup=otd_crops_kb())
    await c.answer()

@router.callback_query(F.data.startswith("otd:tractor:"))
async def otd_pick_tractor(c: CallbackQuery, state: FSMContext):
    name = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    work["machine_name"] = name
    work["machine_type"] = "Трактор"
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_activity)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Вид деятельности трактора:", reply_markup=otd_tractor_work_kb())
    await c.answer()

@router.callback_query(F.data.startswith("otd:twork:"))
async def otd_pick_twork(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
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
    work["location"] = field
    work["location_grp"] = GROUP_FIELDS
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культура:", reply_markup=otd_crops_kb())
    await c.answer()

@router.callback_query(F.data.startswith("otd:hand:"))
async def otd_pick_hand(c: CallbackQuery, state: FSMContext):
    act = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
    work["activity"] = act
    work["act_grp"] = GROUP_HAND
    work["machine_type"] = "Ручная"
    work["machine_name"] = None
    await state.update_data(otd=work)
    await state.set_state(OtdFSM.pick_crop)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культура:", reply_markup=otd_crops_kb())
    await c.answer()

@router.callback_query(F.data.startswith("otd:crop:"))
async def otd_pick_crop(c: CallbackQuery, state: FSMContext):
    crop = c.data.split(":", 2)[2]
    data = await state.get_data()
    work = data.get("otd", {})
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

@router.message(OtdFSM.pick_trips)
async def otd_pick_trips(message: Message, state: FSMContext):
    try:
        trips = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите количество рейсов числом.")
        return
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
    work["location"] = loc
    work["location_grp"] = GROUP_FIELDS
    await state.update_data(otd=work)
    await _otd_to_confirm(c.bot, c.message.chat.id, c.from_user.id, state)
    await c.answer()

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
        await stats_notify_created(bot, rid)
    except Exception:
        pass
    await state.clear()
    text = _format_otd_summary(work)
    role = get_role_label(c.from_user.id)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"✅ Сохранено\n\n{text}", reply_markup=main_menu_kb(role))
    await c.answer("Сохранено")

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
    await state.update_data(brig={"work_date": work_date})
    await state.set_state(BrigFSM.pick_shift)
    kb = InlineKeyboardBuilder()
    kb.button(text="Утренняя", callback_data="brig:shift:morning")
    kb.button(text="Вечерняя", callback_data="brig:shift:evening")
    kb.button(text="🔙 Назад", callback_data="brig:back:date")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Дата: <b>{work_date}</b>\nВыберите смену:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:date")
async def brig_back_date(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👷 Отчет бригадира\nВыберите дату:",
                        reply_markup=_brig_date_kb())
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
        for act in ["Лесополоса", "Прополка", "Сев", "Уборка"]:
            kb.button(text=act, callback_data=f"brig:act:{act}")
        kb.button(text="Прочее", callback_data="brig:act:__other__")
        kb.button(text="🔙 Назад", callback_data="brig:back:mode")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите вид работы:", reply_markup=kb.as_markup())
    else:
        await state.set_state(BrigFSM.pick_machine_kind)
        kb = InlineKeyboardBuilder()
        kb.button(text="Трактор", callback_data="brig:mkind:tractor")
        kb.button(text="КамАЗ", callback_data="brig:mkind:kamaz")
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
    kind = c.data.split(":")[2]
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["tech_kind"] = kind
    await state.update_data(brig=brig)
    if kind == "tractor":
        await state.set_state(BrigFSM.pick_machine_name)
        kb = InlineKeyboardBuilder()
        for name in ["JD7(с)", "JD7(н)", "GD8", "GD6", "Оранжевый", "Погрузчик", "Комбайн"]:
            kb.button(text=name, callback_data=f"brig:mname:{name}")
        kb.button(text="Прочее", callback_data="brig:mname:__other__")
        kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите технику:", reply_markup=kb.as_markup())
    else:
        brig["machine"] = "КамАЗ"
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_kamaz_crop)
        kb = InlineKeyboardBuilder()
        for name in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Навоз", "Прочее"]:
            kb.button(text=name, callback_data=f"brig:kcrop:{name}")
        kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "КамАЗ: выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "brig:back:mkind")
async def brig_back_mkind(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    await state.set_state(BrigFSM.pick_machine_kind)
    kb = InlineKeyboardBuilder()
    kb.button(text="Трактор", callback_data="brig:mkind:tractor")
    kb.button(text="КамАЗ", callback_data="brig:mkind:kamaz")
    kb.button(text="🔙 Назад", callback_data="brig:back:mode")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите тип техники:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("brig:mname:"))
async def brig_pick_machine_name(c: CallbackQuery, state: FSMContext):
    name = c.data.split(":", 2)[2]
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
        brig["machine"] = name
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
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым")
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
    kb = InlineKeyboardBuilder()
    for name in ["JD7(с)", "JD7(н)", "GD8", "GD6", "Оранжевый", "Погрузчик", "Комбайн"]:
        kb.button(text=name, callback_data=f"brig:mname:{name}")
    kb.button(text="Прочее", callback_data="brig:mname:__other__")
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
        for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
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
    act = (message.text or "").strip()
    if not act:
        await message.answer("Поле не может быть пустым")
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine_activity"] = act
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_machine_crop)
    kb = InlineKeyboardBuilder()
    for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
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
    for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
        kb.button(text=crop, callback_data=f"brig:mcrop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mact")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_machine_crop_custom)
async def brig_pick_machine_crop_custom(message: Message, state: FSMContext):
    crop = (message.text or "").strip()
    if not crop:
        await message.answer("Культура не может быть пустой")
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
    for name in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Навоз", "Прочее"]:
        kb.button(text=name, callback_data=f"brig:kcrop:{name}")
    kb.button(text="🔙 Назад", callback_data="brig:back:mkind")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "КамАЗ: выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_kamaz_crop_custom)
async def brig_kamaz_crop_custom(message: Message, state: FSMContext):
    crop = (message.text or "").strip()
    if not crop:
        await message.answer("Культура не может быть пустой")
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["machine_crop"] = crop
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_kamaz_trips)
    await message.answer("Сколько рейсов?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                         ]))

@router.message(BrigFSM.pick_kamaz_trips)
async def brig_kamaz_trips(message: Message, state: FSMContext):
    try:
        trips = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число рейсов",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:kcrop")]
                             ]))
        return
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
    load = (message.text or "").strip()
    if not load:
        await message.answer("Место не может быть пустым")
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
    brig["mode"] = brig.get("mode") or "hand"
    crop = c.data.split(":", 2)[2]
    if crop == "Прочее":
        await state.update_data(brig=brig)
        await state.set_state(BrigFSM.pick_crop_custom)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите культуру текстом:",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                            ]))
    else:
        brig["crop"] = crop
        await state.update_data(brig=brig)
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
    kb = InlineKeyboardBuilder()
    for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
        kb.button(text=crop, callback_data=f"brig:crop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:activity")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_crop_custom)
async def brig_pick_crop_custom(message: Message, state: FSMContext):
    crop = (message.text or "").strip()
    if not crop:
        await message.answer("Культура не может быть пустой")
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["mode"] = brig.get("mode") or "hand"
    brig["crop"] = crop
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_workers)
    await message.answer("Сколько людей работало?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                         ]))

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
        for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
            kb.button(text=crop, callback_data=f"brig:crop:{crop}")
        kb.button(text="🔙 Назад", callback_data="brig:back:activity")
        kb.adjust(2,2)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Выберите культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_activity_custom)
async def brig_pick_activity_custom(message: Message, state: FSMContext):
    act = (message.text or "").strip()
    if not act:
        await message.answer("Поле не может быть пустым",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:activity")]
                             ]))
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["activity"] = act
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_crop)
    kb = InlineKeyboardBuilder()
    for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
        kb.button(text=crop, callback_data=f"brig:crop:{crop}")
    kb.button(text="🔙 Назад", callback_data="brig:back:activity")
    kb.adjust(2,2)
    await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                        "Выберите культуру:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:back:activity")
async def brig_back_activity(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_activity)
    kb = InlineKeyboardBuilder()
    for act in ["Лесополоса", "Прополка", "Сев", "Уборка"]:
        kb.button(text=act, callback_data=f"brig:act:{act}")
    kb.button(text="Прочее", callback_data="brig:act:__other__")
    kb.button(text="🔙 Назад", callback_data="brig:back:mode")
    kb.adjust(2,2)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите вид работы:", reply_markup=kb.as_markup())
    await c.answer()

@router.message(BrigFSM.pick_workers)
async def brig_pick_workers(message: Message, state: FSMContext):
    try:
        workers = int((message.text or "0").strip() or 0)
    except ValueError:
        await message.answer("Введите число людей",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                             ]))
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["workers"] = workers
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_rows)
    await message.answer("Сколько рядов?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:workers")]
                         ]))

@router.callback_query(F.data == "brig:back:workers")
async def brig_back_workers(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_workers)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Сколько людей работало?",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:crop")]
                        ]))
    await c.answer()

@router.message(BrigFSM.pick_rows)
async def brig_pick_rows(message: Message, state: FSMContext):
    try:
        rows = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите число рядов",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:workers")]
                             ]))
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["rows"] = rows
    await state.update_data(brig=brig)
    crop = (brig.get("crop") or "").lower()
    if crop.startswith("карт"):
        await state.set_state(BrigFSM.pick_bags)
        await message.answer("Сколько мешков?",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                             ]))
    else:
        await state.set_state(BrigFSM.pick_field)
        await message.answer("Укажите локацию (поле/место):",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                             ]))

@router.callback_query(F.data == "brig:back:rows")
async def brig_back_rows(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_rows)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Сколько рядов?",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:workers")]
                        ]))
    await c.answer()

@router.message(BrigFSM.pick_bags)
async def brig_pick_bags(message: Message, state: FSMContext):
    try:
        bags = int((message.text or "0").strip() or 0)
    except ValueError:
        await message.answer("Введите число мешков",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                             ]))
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["bags"] = bags
    await state.update_data(brig=brig)
    await state.set_state(BrigFSM.pick_field)
    await message.answer("Укажите локацию (поле/место):",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                         ]))

@router.callback_query(F.data == "brig:back:bags")
async def brig_back_bags(c: CallbackQuery, state: FSMContext):
    await state.set_state(BrigFSM.pick_bags)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Сколько мешков?",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                        ]))
    await c.answer()

@router.message(BrigFSM.pick_field)
async def brig_pick_field(message: Message, state: FSMContext):
    field = (message.text or "").strip()
    if not field:
        await message.answer("Поле не может быть пустым, введите ещё раз",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="brig:back:rows")]
                             ]))
        return
    data = await state.get_data()
    brig = data.get("brig", {})
    brig["field"] = field
    await state.update_data(brig=brig)
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
    await message.answer(summary, reply_markup=kb.as_markup())

@router.callback_query(F.data == "brig:confirm:back")
async def brig_confirm_back(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brig = data.get("brig", {})
    target = brig.get("confirm_back") or "field"
    if target == "tech_crop":
        await state.set_state(BrigFSM.pick_machine_crop)
        kb = InlineKeyboardBuilder()
        for crop in ["Кабачок", "Картошка", "Подсолнечник", "Кукуруза", "Пшеница", "Горох", "Прочее"]:
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
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "✅ Отчет бригадира сохранен", reply_markup=main_menu_kb(get_role_label(c.from_user.id)))
    await c.answer("Сохранено")

@router.callback_query(F.data == "brig:confirm:cancel")
async def brig_confirm_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "Отчет отменен", reply_markup=main_menu_kb(get_role_label(c.from_user.id)))
    await c.answer()

@router.callback_query(F.data == "brig:stats")
async def brig_stats_menu(c: CallbackQuery):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="brig:stats:today")
    kb.button(text="Неделя", callback_data="brig:stats:week")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(2,1)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "Период статистики:", reply_markup=kb.as_markup())
    await c.answer()

def _render_brig_stats(stats: dict, period: str) -> str:
    period_str = "сегодня" if period == "today" else "неделю"
    lines = [f"📊 Статистика за {period_str}:"]
    if stats["zucchini_rows"]:
        lines.append(f"🥒 Кабачок: рядов {stats['zucchini_rows']}, людей {stats['zucchini_workers']}")
    if stats["potato_rows"]:
        lines.append(f"🥔 Картошка: рядов {stats['potato_rows']}, сеток {stats['potato_bags']}, людей {stats['potato_workers']}")
    if stats["details"]:
        lines.append("\nДетали:")
        lines.extend(stats["details"][:10])
    if len(lines) == 1:
        lines.append("Нет данных")
    return "\n".join(lines)

@router.callback_query(F.data.startswith("brig:stats:"))
async def brig_stats_show(c: CallbackQuery):
    if not (is_brigadier(c.from_user.id) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    period = c.data.split(":")[2]
    today = date.today()
    if period == "today":
        start = today
    else:
        start = today - timedelta(days=6)
    stats = fetch_brig_stats(c.from_user.id, start, today)
    text = _render_brig_stats(stats, period)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=main_menu_kb(get_role_label(c.from_user.id)))
    await c.answer()

@router.callback_query(F.data == "tim:party")
async def tim_party(c: CallbackQuery):
    if not is_tim(c.from_user.id):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "👀 Режим наблюдения TIM активен. Доступны: статистика и смена имени.",
                        reply_markup=main_menu_kb("tim"))
    await c.answer()

@router.callback_query(F.data == "it:star")
async def it_star(c: CallbackQuery):
    if not (is_it(c.from_user.id, c.from_user.username) or is_admin(c)):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "⭐ IT панель: используйте /menu для полного списка. Статистика доступна в меню.",
                        reply_markup=main_menu_kb("it"))
    await c.answer()

@router.callback_query(F.data == "menu:edit")
async def cb_menu_edit(c: CallbackQuery):
    rows = user_recent_24h_reports(c.from_user.id)
    if not rows:
        await _send_new_message(c.bot, c.message.chat.id, c.from_user.id,
                            "📝 За последние 48 часов записей нет.",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")]
                            ]))
        await c.answer()
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
    await _send_new_message(c.bot, c.message.chat.id, c.from_user.id, "\n".join(text), reply_markup=kb.as_markup())
    await c.answer()

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
                        "Локации: добавить или удалить", reply_markup=admin_root_loc_kb())
    await c.answer()

@router.callback_query(F.data == "adm:root:act")
async def adm_root_act(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Работы: добавить или удалить", reply_markup=admin_root_act_kb())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech"))
async def adm_root_tech(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    parts = c.data.split(":")
    if len(parts) == 3:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Техника: выберите подгруппу", reply_markup=admin_root_tech_kb())
    else:
        sub = parts[3]
        label = "Трактор" if sub == "tractor" else "КамАЗ"
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            f"Техника ({label}): выберите действие",
                            reply_markup=admin_root_tech_actions_kb(sub))
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop"))
async def adm_root_crop(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Культуры: выбрать действие", reply_markup=admin_root_crop_kb())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:tech:add:"))
async def adm_root_tech_add(c: CallbackQuery):
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

@router.callback_query(F.data.startswith("adm:root:tech:del:"))
async def adm_root_tech_del(c: CallbackQuery):
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

@router.callback_query(F.data.startswith("adm:root:tech:delpick:"))
async def adm_root_tech_delpick(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    name = c.data.split(":", 3)[3].replace("_", " ")
    remove_activity(name)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Техника '{name}' удалена.", reply_markup=admin_root_tech_kb())
    await c.answer("Удалено")

@router.callback_query(F.data == "adm:root:crop:add")
async def adm_root_crop_add(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.add_name)
    await state.update_data(admin_kind="crop", admin_grp="crop")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите название культуры:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:root:crop")],
                            [InlineKeyboardButton(text="⬅️ В корень", callback_data="adm:root")]
                        ]))
    await c.answer()

@router.callback_query(F.data == "adm:root:crop:del")
async def adm_root_crop_del(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    items = list_crops()
    kb = InlineKeyboardBuilder()
    if items:
        for it in items:
            safe = it.replace(":", "_")[:20]
            kb.button(text=f"🗑 {it}", callback_data=f"adm:root:crop:delpick:{safe}")
        kb.adjust(2)
    else:
        kb.button(text="— список пуст —", callback_data="adm:root:crop")
    kb.button(text="🔙 Назад", callback_data="adm:root:crop")
    kb.button(text="⬅️ В корень", callback_data="adm:root")
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Удалить культуру:", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("adm:root:crop:delpick:"))
async def adm_root_crop_delpick(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    name = c.data.split(":", 3)[3].replace("_", " ")
    remove_crop(name)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Культура '{name}' удалена.", reply_markup=admin_root_crop_kb())
    await c.answer("Удалено")

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
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите user_id, которому выдать роль бригадира:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles")]
                        ]))
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
        await message.answer("Укажите user_id или @username известного боту.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles")]
                             ]))
        return
    set_role(target_id, "brigadier", message.from_user.id)
    add_brigadier(target_id, None, None, message.from_user.id)
    await state.clear()
    await message.answer(f"Роль бригадира выдана пользователю {target_id}",
                         reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:role:del:brig")
async def adm_role_del_brig(c: CallbackQuery, state: FSMContext):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await state.set_state(AdminFSM.del_brig_id)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Введите user_id, у которого снять роль бригадира:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles")]
                        ]))
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
        await message.answer("Укажите user_id или @username известного боту.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:roles")]
                             ]))
        return
    clear_role(target_id, "brigadier")
    remove_brigadier(target_id)
    await state.clear()
    await message.answer(f"Роль бригадира снята с пользователя {target_id}",
                         reply_markup=admin_menu_kb())

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

# -------------- Статистика кнопки --------------

@router.callback_query(F.data == "stats:today")
async def cb_stats_today(c: CallbackQuery):
    await show_stats_today(c.message.chat.id, c.from_user.id, is_admin(c))
    await c.answer()

@router.callback_query(F.data == "stats:week")
async def cb_stats_week(c: CallbackQuery):
    await show_stats_week(c.message.chat.id, c.from_user.id, is_admin(c))
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
    work["location"] = loc
    await state.update_data(work=work)
    await state.set_state(WorkFSM.pick_date)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>дату</b>:", reply_markup=days_keyboard())
    await c.answer()

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
        await stats_notify_created(bot, rid)
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
    role = get_role_label(c.from_user.id)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=main_menu_kb(role))
    await c.answer()

# -------------- Перепись: удалить/изменить -------------

@router.callback_query(F.data.startswith("edit:del:"))
async def cb_edit_delete(c: CallbackQuery):
    rid = int(c.data.split(":")[2])
    ok = delete_report(rid, c.from_user.id)
    if ok:
        await c.answer("Удалено")
    else:
        await c.answer("Не получилось удалить (возможно, запись не ваша или старше 24ч)", show_alert=True)
    # Обновим сводку в статистике (если была удалена)
    if ok:
        try:
            await stats_notify_deleted(bot, rid)
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
            await stats_notify_changed(bot, rid)
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
            await stats_notify_changed(bot, rid)
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
                await stats_notify_changed(bot, rid)
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
    data = await state.get_data()
    rid = data.get("edit_id")
    grp = data.get("edit_grp")
    
    if not rid or not grp:
        await message.answer("Ошибка: данные не найдены. Начните заново.")
        return
    
    act_name = (message.text or "").strip()
    if not act_name:
        await message.answer("Введите название работы.")
        return
    
    # Обновляем активность
    grp_name = GROUP_TECH if grp == "tech" else GROUP_HAND
    ok = update_report_activity(rid, message.from_user.id, act_name, grp_name)
    
    if ok:
        queue_active = (await state.get_data()).get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(bot, rid)
        except Exception:
            pass
        await message.answer("Вид работы обновлен")
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await message.answer("Не получилось обновить вид работы")

@router.message(EditFSM.waiting_new_machine)
async def cb_edit_machine(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await message.answer("Ошибка: данные не найдены. Начните заново.")
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите технику, например: Трактор JD8")
        return
    parts = text.split()
    machine_type = parts[0]
    machine_name = " ".join(parts[1:]) if len(parts) > 1 else None
    ok = update_report_machine(int(rid), message.from_user.id, machine_type, machine_name)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(bot, int(rid))
        except Exception:
            pass
        await message.answer("Техника обновлена")
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await message.answer("Не получилось обновить технику")

@router.message(EditFSM.waiting_new_crop)
async def cb_edit_crop(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await message.answer("Ошибка: данные не найдены. Начните заново.")
        return
    crop = (message.text or "").strip()
    if not crop:
        await message.answer("Введите название культуры.")
        return
    ok = update_report_crop(int(rid), message.from_user.id, crop)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(bot, int(rid))
        except Exception:
            pass
        await message.answer("Культура обновлена")
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await message.answer("Не получилось обновить культуру")

@router.message(EditFSM.waiting_new_trips)
async def cb_edit_trips(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await message.answer("Ошибка: данные не найдены. Начните заново.")
        return
    try:
        trips = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите количество рейсов числом.")
        return
    ok = update_report_trips(int(rid), message.from_user.id, trips)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(bot, int(rid))
        except Exception:
            pass
        await message.answer("Количество рейсов обновлено")
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await message.answer("Не получилось обновить рейсы")

@router.message(EditFSM.waiting_new_date)
async def cb_edit_date(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("edit_id")
    if not rid:
        await message.answer("Ошибка: данные не найдены. Начните заново.")
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
        await message.answer("Неверный формат даты. Используйте ГГГГ-ММ-ДД или ДД.ММ.ГГ.")
        return
    ok = update_report_date(int(rid), message.from_user.id, new_date)
    if ok:
        queue_active = data.get("edit_queue_active")
        if queue_active:
            await state.update_data(edit_queue_active=True)
        else:
            await state.clear()
        try:
            await stats_notify_changed(bot, int(rid))
        except Exception:
            pass
        await message.answer("Дата обновлена")
        if queue_active:
            await _start_next_edit_in_queue(message.bot, message.chat.id, message.from_user.id, state)
        else:
            await cb_menu_edit_from_message(message)
    else:
        await message.answer("Не получилось обновить дату")

async def cb_menu_edit_from_message(message: Message):
    """Вспомогательная функция для возврата к меню редактирования из текстового сообщения"""
    rows = user_recent_24h_reports(message.from_user.id)
    if not rows:
        await message.answer("📝 За последние 48 часов записей нет.")
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
    await message.answer("\n".join(text), reply_markup=kb.as_markup())

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
    name = (message.text or "").strip()
    ok = False
    if kind == "act":
        ok = add_activity(GROUP_TECH if grp=="tech" else GROUP_HAND, name)
    else:
        ok = add_location(GROUP_FIELDS if grp=="fields" else GROUP_WARE, name)
    await state.clear()
    if ok:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            f"✅ Добавлено: <b>{name}</b>", reply_markup=admin_menu_kb())
    else:
        await _edit_or_send(message.bot, message.chat.id, message.from_user.id,
                            f"⚠️ Не получилось (возможно, уже есть): <b>{name}</b>", reply_markup=admin_menu_kb())

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
        count, message = await asyncio.to_thread(export_reports_to_sheets)
        
        if count > 0:
            text = f"✅ {message}"
        else:
            text = f"ℹ️ {message}"
        
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

@router.message(F.text)
async def any_text(message: Message):
    u = get_user(message.from_user.id)
    await show_main_menu(message.chat.id, message.from_user.id, u, "Меню")

# -----------------------------
# main() и запуск (v3 Dispatcher/Router)
# -----------------------------

bot: Bot
dp: Dispatcher
scheduler: Optional[AsyncIOScheduler] = None

async def scheduled_export():
    """Задача для автоматического экспорта"""
    try:
        logging.info("Running scheduled export...")
        count, message = export_reports_to_sheets()
        logging.info(f"Scheduled export result: {message}")
        
        # Проверяем создание таблицы для следующего месяца
        created, sheet_msg = check_and_create_next_month_sheet()
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
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler:
            scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
    



















