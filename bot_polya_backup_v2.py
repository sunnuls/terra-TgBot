# bot_polya.py
# -*- coding: utf-8 -*-

import asyncio
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple, List

from aiogram.client.default import DefaultBotProperties
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
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from dotenv import load_dotenv

# -----------------------------
# Конфиг
# -----------------------------

load_dotenv()\n\nlogging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в .env")

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

DB_PATH = os.path.join(os.getcwd(), "reports.db")

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
            c.execute("UPDATE users SET full_name=?, username=?, tz=?, created_at=? WHERE user_id=?",
                      (full_name, username, tz, now, user_id))
        else:
            c.execute("INSERT INTO users(user_id, full_name, username, tz, created_at) VALUES(?,?,?,?,?)",
                      (user_id, full_name, username, tz, now))
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

def remove_location(name: str) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM locations WHERE name=?", (name,))
        con.commit()
        return cur.rowcount > 0

def insert_report(user_id:int, reg_name:str, username:str, location:str, loc_grp:str,
                  activity:str, act_grp:str, work_date:str, hours:int, chat_id:int) -> int:
    now = datetime.now().isoformat()
    with connect() as con, closing(con.cursor()) as c:
        c.execute("""
        INSERT INTO reports(created_at, user_id, reg_name, username, location, location_grp,
                            activity, activity_grp, work_date, hours, chat_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (now, user_id, reg_name, username, location, loc_grp, activity, act_grp, work_date, hours, chat_id))
        con.commit()
        return c.lastrowid

def get_report(report_id:int):
    with connect() as con, closing(con.cursor()) as c:
        r = c.execute(
            "SELECT id, created_at, user_id, reg_name, username, location, location_grp, activity, activity_grp, work_date, hours, chat_id FROM reports WHERE id=?",
            (report_id,)
        ).fetchone()
        if not r:
            return None
        return {
            "id": r[0], "created_at": r[1], "user_id": r[2], "reg_name": r[3], "username": r[4],
            "location": r[5], "location_grp": r[6], "activity": r[7], "activity_grp": r[8],
            "work_date": r[9], "hours": r[10], "chat_id": r[11]
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
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    with connect() as con, closing(con.cursor()) as c:
        rows = c.execute("""
        SELECT id, work_date, activity, location, hours, created_at
        FROM reports
        WHERE user_id=? AND created_at>=?
        ORDER BY created_at DESC
        """, (user_id, cutoff)).fetchall()
        return rows

def delete_report(report_id:int, user_id:int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("DELETE FROM reports WHERE id=? AND user_id=?", (report_id, user_id))
        con.commit()
        return cur.rowcount > 0

def update_report_hours(report_id:int, user_id:int, new_hours:int) -> bool:
    with connect() as con, closing(con.cursor()) as c:
        cur = c.execute("UPDATE reports SET hours=? WHERE id=? AND user_id=?", (new_hours, report_id, user_id))
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

class AdminFSM(StatesGroup):
    add_group = State()
    add_name = State()
    del_group = State()
    del_pick = State()

class EditFSM(StatesGroup):
    waiting_new_hours = State()

# -----------------------------
# Вспомогалки: одно-сообщение и проверки
# -----------------------------

# где хранить последнее сообщение (chat_id, user_id) -> message_id
last_message: Dict[Tuple[int, int], int] = {}

def is_admin(message_or_query) -> bool:
    uid = message_or_query.from_user.id
    uname = (message_or_query.from_user.username or "").lower().lstrip("@")
    if uid in ADMIN_IDS:
        return True
    if uname and uname in ADMIN_USERNAMES:
        return True
    return False

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
        except TelegramBadRequest:
            pass
    # Если настроен рабочий топик, отправим сообщение именно туда
    m = await bot.send_message(target_chat_id, text, reply_markup=reply_markup, **extra)
    last_message[key] = m.message_id

def reply_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🧰 Меню")]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )

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

def main_menu_kb(admin: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚜 Работа", callback_data="menu:work")
    kb.button(text="📊 Статистика", callback_data="menu:stats")
    kb.button(text="📝 Перепись", callback_data="menu:edit")
    kb.button(text="✏️ Изменить имя", callback_data="menu:name")
    if admin:
        kb.button(text="⚙️ Админ", callback_data="menu:admin")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

def work_groups_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Техника", callback_data="work:grp:tech")
    kb.button(text="Ручная", callback_data="work:grp:hand")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(2, 1)
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
    kb.button(text="➕ Добавить работу", callback_data="adm:add:act")
    kb.button(text="➖ Удалить работу", callback_data="adm:del:act")
    kb.button(text="➕ Добавить локацию", callback_data="adm:add:loc")
    kb.button(text="➖ Удалить локацию", callback_data="adm:del:loc")
    kb.button(text="🔙 Назад", callback_data="menu:root")
    kb.adjust(2,2,1)
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
# Бот
# -----------------------------





if ROBOT_CHAT_ID is not None and ROBOT_TOPIC_ID is not None:
    @router.message(F.chat.id == ROBOT_CHAT_ID, F.message_thread_id == ROBOT_TOPIC_ID)
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
    @router.message(F.chat.id == STATS_CHAT_ID, F.message_thread_id == STATS_TOPIC_ID)
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
    if not is_admin(message):
        return
    await ensure_robot_banner(message.bot, force_new=True)
    await message.answer("Robot banner refreshed.")

# -------------- Команды --------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    init_db()
    upsert_user(
        message.from_user.id,
        (message.from_user.full_name or "").strip(),
        TZ,
        message.from_user.username or "",
    )
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
    await show_stats_today(message.chat.id, message.from_user.id, is_admin(message), via_command=True)

@router.message(Command("my"))
async def cmd_my(message: Message):
    await show_stats_week(message.chat.id, message.from_user.id, is_admin(message), via_command=True)

# Доп. команды для удобства в группах с топиками
@router.message(Command("where"))
async def cmd_where(message: Message):
    # Покажем chat_id и message_thread_id, чтобы внести в .env
    tid = getattr(message, "message_thread_id", None)
    await message.answer(
        f"chat_id: <code>{message.chat.id}</code>\n"
        f"thread_id: <code>{tid if tid is not None else '-'}""</code>\n"
        f"user_id: <code>{message.from_user.id}</code>")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    u = get_user(message.from_user.id)
    await show_main_menu(message.chat.id, message.from_user.id, u, "Главное меню:")

@router.message(F.text == "🧰 Меню")
async def msg_persistent_menu(message: Message):
    u = get_user(message.from_user.id)
    await show_main_menu(message.chat.id, message.from_user.id, u, "Главное меню:")

# -------------- Регистрация --------------

@router.message(NameFSM.waiting_name)
async def capture_full_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 3 or " " not in text:
        await message.answer("Введите Фамилию и Имя (через пробел). Пример: <b>Иванов Иван</b>")
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
        await show_main_menu(message.chat.id, message.from_user.id, u, f"✏️ Имя изменено на: <b>{text}</b>")

# -------------- Рисовалки экранов --------------

async def show_main_menu(chat_id:int, user_id:int, u:dict, header:str):
    class Dummy: pass
    dummy = Dummy()
    dummy.from_user = Dummy()
    dummy.from_user.id = user_id
    dummy.from_user.username = (u or {}).get("username")
    admin = is_admin(dummy)

    # у обычных статистика — без ФИО, а шапка остаётся
    name = (u or {}).get("full_name") or "—"
    text = f"👤 <b>{name}</b>\n\nВыберите действие:"
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=main_menu_kb(admin))

async def show_stats_today(chat_id:int, user_id:int, admin:bool, via_command=False):
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
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=main_menu_kb(admin))

async def show_stats_week(chat_id:int, user_id:int, admin:bool, via_command=False):
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
    await _edit_or_send(bot, chat_id, user_id, text, reply_markup=main_menu_kb(admin))

# -------------- Меню --------------

@router.callback_query(F.data == "menu:root")
async def cb_menu_root(c: CallbackQuery):
    u = get_user(c.from_user.id)
    await show_main_menu(c.message.chat.id, c.from_user.id, u, "Меню")
    await c.answer()

@router.callback_query(F.data == "menu:work")
async def cb_menu_work(c: CallbackQuery, state: FSMContext):
    u = get_user(c.from_user.id)
    if not u or not (u.get("full_name") or "").strip():
        await state.set_state(NameFSM.waiting_name)
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "Введите <b>Фамилию Имя</b> для регистрации.")
        await c.answer()
        return
    await state.update_data(work={})
    await state.set_state(WorkFSM.pick_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>тип работы</b>:", reply_markup=work_groups_kb())
    await c.answer()

@router.callback_query(F.data == "menu:stats")
async def cb_menu_stats(c: CallbackQuery):
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите период статистики:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Сегодня", callback_data="stats:today")],
                            [InlineKeyboardButton(text="Неделя", callback_data="stats:week")],
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")],
                        ]))
    await c.answer()

@router.callback_query(F.data == "menu:edit")
async def cb_menu_edit(c: CallbackQuery):
    rows = user_recent_24h_reports(c.from_user.id)
    if not rows:
        await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                            "📝 За последние 24 часа записей нет.",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")]
                            ]))
        await c.answer()
        return
    kb = InlineKeyboardBuilder()
    text = ["📝 <b>Ваши записи за последние 24 часа</b>:"]
    for rid, d, act, loc, h, created in rows:
        text.append(f"• #{rid} {d} | {loc} — {act}: <b>{h}</b> ч")
        kb.row(
            InlineKeyboardButton(text=f"🖊 Изменить #{rid}", callback_data=f"edit:chg:{rid}:{d}"),
            InlineKeyboardButton(text=f"🗑 Удалить #{rid}", callback_data=f"edit:del:{rid}")
        )
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root"))
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, "\n".join(text), reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data == "menu:admin")
async def cb_menu_admin(c: CallbackQuery):
    if not is_admin(c):
        await c.answer("Нет прав", show_alert=True)
        return
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "⚙️ <b>Админ-панель</b>:", reply_markup=admin_menu_kb())
    await c.answer()

# -------------- Изменение имени --------------

@router.callback_query(F.data == "menu:name")
async def cb_menu_name(c: CallbackQuery, state: FSMContext):
    await state.set_state(NameFSM.waiting_name)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "✏️ Введите <b>Фамилию Имя</b> для изменения (например: <b>Иванов Иван</b>):",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:root")]
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
    await state.set_state(WorkFSM.pick_group)
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        "Выберите <b>тип работы</b>:", reply_markup=work_groups_kb())
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
@router.message(F.text & F.text.len() > 0, ~StateFilter(AdminFSM.add_name), ~StateFilter(NameFSM.waiting_name))
async def maybe_capture_custom_activity(message: Message, state: FSMContext):
    data = await state.get_data()
    grp_name = data.get("awaiting_custom_activity")
    if not grp_name:
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
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id, text, reply_markup=main_menu_kb(is_admin(c)))
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
    await state.set_state(EditFSM.waiting_new_hours)
    await state.update_data(edit_id=rid, edit_date=work_d)
    # клавиатура на популярные значения + назад
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(h), callback_data=f"edit:h:{h}") for h in (1,2,3,4)],
        [InlineKeyboardButton(text=str(h), callback_data=f"edit:h:{h}") for h in (5,6,7,8)],
        [InlineKeyboardButton(text=str(h), callback_data=f"edit:h:{h}") for h in (9,10,12,16)],
        [InlineKeyboardButton(text=str(h), callback_data=f"edit:h:{h}") for h in (20,22,24)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:edit")],
    ])
    await _edit_or_send(c.bot, c.message.chat.id, c.from_user.id,
                        f"Укажите <b>новое количество часов</b> для записи #{rid} ({work_d})",
                        reply_markup=kb)
    await c.answer()

@router.callback_query(F.data.startswith("edit:h:"))
async def cb_edit_hours_value(c: CallbackQuery, state: FSMContext):
    new_h = int(c.data.split(":")[2])
    data = await state.get_data()
    rid = int(data.get("edit_id"))
    work_d = data.get("edit_date")
    # лимит 24
    already = sum_hours_for_user_date(c.from_user.id, work_d, exclude_report_id=rid)
    if already + new_h > 24:
        await c.answer("❗ В сутки нельзя больше 24 ч. Выберите меньшее число.", show_alert=True)
        return
    ok = update_report_hours(rid, c.from_user.id, new_h)
    if ok:
        await state.clear()
        try:
            await stats_notify_changed(bot, rid)
        except Exception:
            pass
        await c.answer("Обновлено")
        await cb_menu_edit(c)
    else:
        await c.answer("Не получилось обновить", show_alert=True)

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

# -------------- Фолбэк на текст вне ожиданий --------------

@router.message(F.text)
async def any_text(message: Message):
    u = get_user(message.from_user.id)
    await show_main_menu(message.chat.id, message.from_user.id, u, "Меню")

# -----------------------------
# main()
# -----------------------------

async def main():
    init_db()
    # команды для меню (команд)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Запуск"),
            BotCommand(command="today", description="Статистика за сегодня"),
            BotCommand(command="my", description="Моя статистика (неделя)"),
            BotCommand(command="menu", description="Открыть меню бота"),
            BotCommand(command="where", description="Показать chat_id и thread_id"),
        ])
    except Exception:
        pass

    print("[main] db initialized")
    await ensure_robot_banner(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
    



















