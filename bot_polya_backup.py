#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Полевая учётка — регистрация Фамилия Имя, меню с кнопками,
иерархия локаций (группа: поля/склад → выбор конкретного поля),
кнопка Назад на каждом шаге, команды /today и /my,
права админа на общую статистику, и автоэкспорт Excel на Google Drive
(ежедневно 23:59, файл Reports-YYYY-MM.xlsx).
"""

import asyncio
import csv
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from pathlib import Path
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

APP_VERSION = "build-2025-08-29-menu-back-stats-hours-fix"

# ========== UI helpers: правим одно сообщение вместо новых ==========
from aiogram.exceptions import TelegramBadRequest

async def edit_only(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None):
    """
    Безопасно редактирует существующее сообщение.
    Если текст не менялся — обновляет только клавиатуру.
    """
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            try:
                await cq.message.edit_reply_markup(reply_markup=kb)
            except TelegramBadRequest:
                pass
        else:
            raise
    finally:
        # обязательно отвечаем на callback, чтобы не висела «загрузка»
        try:
            await cq.answer()
        except Exception:
            pass
# ===================================================================

dp = Dispatcher()
CFG = None
TZ: ZoneInfo = None

# ---------------- Конфиг ----------------
@dataclass
class Config:
    token: str
    tz: str
    admin_ids: List[int]
    admin_usernames: List[str]
    sa_json: str
    drive_folder_id: str


def _split_csv(env_value: str) -> List[str]:
    return [s.strip() for s in (env_value or "").split(",") if s.strip()]


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN not set in .env")

    tz = os.getenv("TZ", "Europe/Moscow").strip()

    raw_admins = _split_csv(os.getenv("ADMIN_IDS", ""))
    admin_ids: List[int] = []
    admin_usernames: List[str] = []
    for item in raw_admins:
        if item.isdigit():
            admin_ids.append(int(item))
        else:
            admin_usernames.append(item.lstrip("@").lower())

    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    drive_folder_id = os.getenv("DRIVE_FOLDER_ID", "").strip()

    return Config(
        token=token,
        tz=tz,
        admin_ids=admin_ids,
        admin_usernames=admin_usernames,
        sa_json=sa_json,
        drive_folder_id=drive_folder_id,
    )


def is_admin_user(user_id: int, username: Optional[str], cfg: Config) -> bool:
    if user_id in cfg.admin_ids:
        return True
    if username and username.lower() in cfg.admin_usernames:
        return True
    return False


# ---------------- БД ----------------
DB_PATH = Path("reports.db")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                full_name TEXT,
                username TEXT,
                location TEXT NOT NULL,
                activity TEXT NOT NULL,
                work_date TEXT NOT NULL,
                hours INTEGER NOT NULL,
                chat_id INTEGER NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS loc_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_id INTEGER,
                FOREIGN KEY (group_id) REFERENCES loc_groups (id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL
            )
            """
        )
        # миграция на случай старой схемы без full_name
        if not _column_exists(conn, "reports", "full_name"):
            c.execute("ALTER TABLE reports ADD COLUMN full_name TEXT")
        
        # Добавляем базовые группы локаций
        c.execute("INSERT OR IGNORE INTO loc_groups (name) VALUES ('поля')")
        c.execute("INSERT OR IGNORE INTO loc_groups (name) VALUES ('склад')")
        
        # Добавляем базовые локации
        for field in FIELDS:
            c.execute("INSERT OR IGNORE INTO locations (name, group_id) VALUES (?, (SELECT id FROM loc_groups WHERE name = 'поля'))", (field,))
        
        # Добавляем базовые виды работ
        for activity in TECH_ACTIVITIES:
            c.execute("INSERT OR IGNORE INTO activities (name, kind) VALUES (?, 'tech')", (activity,))
        for activity in MANUAL_ACTIVITIES:
            c.execute("INSERT OR IGNORE INTO activities (name, kind) VALUES (?, 'manual')", (activity,))
        
        conn.commit()


def upsert_user(user_id: int, full_name: str, tz: ZoneInfo, username: Optional[str] = None) -> None:
    now = datetime.now(tz).isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO users (user_id, full_name, username, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, username=excluded.username
            """,
            (user_id, full_name, username, now),
        )
        conn.commit()


def get_registered_name(user_id: int) -> Optional[str]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        return row[0] if row else None


def insert_report(
    created_at: str,
    user_id: int,
    full_name: str,
    username: Optional[str],
    location: str,
    activity: str,
    work_date: str,
    hours: int,
    chat_id: int,
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO reports
              (created_at, user_id, full_name, username, location, activity, work_date, hours, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (created_at, user_id, full_name, username, location, activity, work_date, hours, chat_id),
        )
        conn.commit()


def fetch_reports_between(
    start: date,
    end: date,
    for_user_id: Optional[int] = None,
) -> List[Tuple[str, str, str, str, str, int]]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        sql = """
            SELECT work_date, full_name, username, location, activity, hours
            FROM reports
            WHERE date(work_date) >= date(?) AND date(work_date) <= date(?)
        """
        params: List = [start.isoformat(), end.isoformat()]
        if for_user_id is not None:
            sql += " AND user_id = ?"
            params.append(for_user_id)
        sql += " ORDER BY work_date ASC, created_at ASC"
        c.execute(sql, tuple(params))
        return c.fetchall()


# ---------------- Константы локаций ----------------
LOCATION_GROUPS = ["поля", "склад"]
FIELDS = [
    "Северное", "Фазенда", "5 га", "58 га", "Фермерское", "Сад",
    "Чеки №1", "Чеки №2", "Чеки №3", "Рогачи (б)", "Рогачи(М)",
    "Владимирова Аренда", "МТФ"
]


# ---------------- Клавиатуры ----------------
def rows(items: List[InlineKeyboardButton], n: int) -> List[List[InlineKeyboardButton]]:
    return [items[i:i + n] for i in range(0, len(items), n)]


def kb_back_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ]
        ]
    )


def main_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🚜 Работа", callback_data="menu:work")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats")],
        [InlineKeyboardButton(text="✏️ Изменить имя", callback_data="menu:name")],
        [InlineKeyboardButton(text="📝 Перепись (24ч)", callback_data="menu:edit24")],
    ]
    if is_admin:
        rows.insert(0, [InlineKeyboardButton(text="⚙️ Админ", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Добавить локацию", callback_data="adm:add_loc")],
        [InlineKeyboardButton(text="➖ Удалить локацию", callback_data="adm:del_loc")],
        [InlineKeyboardButton(text="➕ Добавить вид работы (Техника)", callback_data="adm:add_act_tech")],
        [InlineKeyboardButton(text="➕ Добавить вид работы (Ручная)", callback_data="adm:add_act_manual")],
        [InlineKeyboardButton(text="➖ Удалить вид работы", callback_data="adm:del_act")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def show_main_menu_cq(cq: CallbackQuery):
    await edit_only(
        cq,
        "Главное меню",
        main_menu_kb(is_admin_user(cq.from_user.id, cq.from_user.username, CFG)),
    )

@dp.callback_query(F.data == "menu:admin")
async def open_admin(cq: CallbackQuery):
    await edit_only(cq, "⚙️ Админ-панель", admin_keyboard())


@dp.callback_query(F.data.startswith("back:"))
async def on_back(cq: CallbackQuery):
    dest = cq.data.split(":", 1)[1]
    if dest == "menu":
        return await show_main_menu_cq(cq)
    if dest == "admin":
        return await edit_only(cq, "⚙️ Админ-панель", admin_keyboard())
    # по умолчанию просто закроем загрузку
    await cq.answer("Назад недоступен.", show_alert=True)

import sqlite3

DB_PATH = "reports.db"  # если у тебя переменная называется иначе — подставь её
# ——— Удалить локацию
@dp.callback_query(F.data == "adm:del_loc")
async def adm_del_loc(cq: CallbackQuery):
    items = db_all_locations()
    if not items:
        await cq.answer("Список локаций пуст", show_alert=True)
        return await edit_only(cq, "⚙️ Админ-панель", admin_keyboard())
    # соберём клавиатуру
    pairs = [(f"🗑 {title}", f"del_loc:{loc_id}") for loc_id, title in items]
    # небольшой универсальный билдер рядов
    kb_rows, row, per_row = [], [], 2
    for i, (txt, cb) in enumerate(pairs, 1):
        row.append(InlineKeyboardButton(text=txt, callback_data=cb))
        if i % per_row == 0:
            kb_rows.append(row); row = []
    if row: kb_rows.append(row)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:admin")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await edit_only(cq, "Выберите локацию для удаления:", kb)

@dp.callback_query(F.data.startswith("del_loc:"))
async def _del_loc(cq: CallbackQuery):
    loc_id = int(cq.data.split(":", 1)[1])
    db_delete_location(loc_id)
    await cq.answer("Удалено")
    return await adm_del_loc(cq)

# ——— Удалить вид работы
@dp.callback_query(F.data == "adm:del_act")
async def adm_del_act(cq: CallbackQuery):
    items = db_all_activities()
    if not items:
        await cq.answer("Список видов работ пуст", show_alert=True)
        return await edit_only(cq, "⚙️ Админ-панель", admin_keyboard())
    pairs = [(f"🗑 {title}", f"del_act:{aid}") for aid, title in items]
    kb_rows, row, per_row = [], [], 2
    for i, (txt, cb) in enumerate(pairs, 1):
        row.append(InlineKeyboardButton(text=txt, callback_data=cb))
        if i % per_row == 0:
            kb_rows.append(row); row = []
    if row: kb_rows.append(row)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:admin")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await edit_only(cq, "Выберите вид работы для удаления:", kb)

@dp.callback_query(F.data.startswith("del_act:"))
async def _del_act(cq: CallbackQuery):
    act_id = int(cq.data.split(":", 1)[1])
    db_delete_activity(act_id)
    await cq.answer("Удалено")
    return await adm_del_act(cq)


# ——— Добавить локацию
@dp.callback_query(F.data == "adm:add_loc")
async def adm_add_loc(cq: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Поля", callback_data="adm:add_loc_kind:fields"),
            InlineKeyboardButton(text="Склад", callback_data="adm:add_loc_kind:storage"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:admin")]
    ])
    await edit_only(cq, "Выберите группу для новой локации:", kb)


@dp.callback_query(F.data.startswith("adm:add_loc_kind:"))
async def adm_add_loc_kind(cq: CallbackQuery):
    kind = cq.data.split(":", 1)[1]
    await cq.message.edit_text(
        f"Введите название новой локации (группа: {kind}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:add_loc")]
        ])
    )
    # Здесь нужно добавить состояние для ожидания ввода названия локации


# ——— Добавить вид работы
@dp.callback_query(F.data == "adm:add_act_tech")
async def adm_add_act_tech(cq: CallbackQuery):
    await cq.message.edit_text(
        "Введите название нового вида работы (техника):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:admin")]
        ])
    )
    # Здесь нужно добавить состояние для ожидания ввода названия работы


@dp.callback_query(F.data == "adm:add_act_manual")
async def adm_add_act_manual(cq: CallbackQuery):
    await cq.message.edit_text(
        "Введите название нового вида работы (ручная):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:admin")]
        ])
    )
    # Здесь нужно добавить состояние для ожидания ввода названия работы

async def send_stats(user_id: Optional[int], message: Message, range_days: int, title: str, is_admin: bool, edit_with_callback: Optional[CallbackQuery] = None):
    """Отправляет статистику, поддерживает как обычные сообщения, так и редактирование через callback."""
    today = datetime.now(TZ).date()
    if range_days == 1:
        start = end = today
    else:
        start = today - timedelta(days=range_days-1)
        end = today

    rows = fetch_reports_between(start, end, for_user_id=None if is_admin else user_id)
    if not rows:
        scope = "всех" if is_admin else "ваши"
        text = f"Записей {title} ({scope}) нет."
        if edit_with_callback:
            await edit_with_callback.message.edit_text(text, reply_markup=kb_stats_menu())
        else:
            await message.answer(text)
        return

    total = sum(r[5] for r in rows)
    lines = [f"<b>Статистика {title}:</b> всего часов: <b>{total}</b>"]
    for i, (wd, reg, uname, loc, act, hrs) in enumerate(rows[:20], 1):
        who = reg or (f"@{uname}" if uname else "-")
        lines.append(f"{i}. {wd} • {who} • {loc} • {act} — <b>{hrs}</b> ч")
    if len(rows) > 20:
        lines.append(f"... и ещё {len(rows)-20} записей")
    
    text = "\n".join(lines)
    if edit_with_callback:
        await edit_with_callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_stats_menu())
    else:
        await message.answer(text, parse_mode=ParseMode.HTML)


@dp.callback_query(F.data == "stat:today")
async def stat_today_cq(cq: CallbackQuery):
    admin = is_admin_user(cq.from_user.id, cq.from_user.username, CFG)
    await send_stats(
        user_id=None if admin else cq.from_user.id,
        message=cq.message,
        range_days=1,
        title="Сегодня",
        is_admin=admin,
        edit_with_callback=cq
    )


def db_all_locations() -> list[tuple[int, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT l.id AS id,
                   COALESCE(g.name || ' · ', '') || l.name AS title
            FROM locations l
            LEFT JOIN loc_groups g ON g.id = l.group_id
            ORDER BY g.name NULLS FIRST, l.name
        """).fetchall()
    return [(r["id"], r["title"]) for r in rows]

def db_delete_location(loc_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM locations WHERE id=?", (loc_id,))
        conn.commit()

def db_all_activities() -> list[tuple[int, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT a.id AS id,
                   (CASE WHEN a.kind='tech' THEN 'Техника'
                         WHEN a.kind='manual' THEN 'Ручная'
                         ELSE 'Другое' END) || ' · ' || a.name AS title
            FROM activities a
            ORDER BY a.kind, a.name
        """).fetchall()
    return [(r["id"], r["title"]) for r in rows]

def db_delete_activity(act_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM activities WHERE id=?", (act_id,))
        conn.commit()


def add_location(name: str, kind: str):
    """Добавляет новую локацию в базу данных."""
    with sqlite3.connect(DB_PATH) as conn:
        # Определяем group_id на основе kind
        if kind == "fields":
            group_name = "поля"
        elif kind == "storage":
            group_name = "склад"
        else:
            group_name = kind
        
        # Получаем или создаем group_id
        c = conn.cursor()
        c.execute("SELECT id FROM loc_groups WHERE name = ?", (group_name,))
        result = c.fetchone()
        if result:
            group_id = result[0]
        else:
            c.execute("INSERT INTO loc_groups (name) VALUES (?)", (group_name,))
            group_id = c.lastrowid
        
        # Добавляем локацию
        c.execute("INSERT INTO locations (name, group_id) VALUES (?, ?)", (name, group_id))
        conn.commit()


def add_activity(name: str, category: str):
    """Добавляет новый вид работы в базу данных."""
    with sqlite3.connect(DB_PATH) as conn:
        # Определяем kind на основе category
        if category == "tech":
            kind = "tech"
        elif category == "manual":
            kind = "manual"
        else:
            kind = "other"
        
        c = conn.cursor()
        c.execute("INSERT INTO activities (name, kind) VALUES (?, ?)", (name, kind))
        conn.commit()
 

def kb_stats_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="stats:today"),
                InlineKeyboardButton(text="Неделя", callback_data="stats:week"),
            ],
            *kb_back_cancel().inline_keyboard,
        ]
    )

 
def kb_work_types() -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(text="🚜 техника", callback_data="wtype:техника"),
        InlineKeyboardButton(text="🧰 ручная", callback_data="wtype:ручная"),
    ]
    ik = rows(btns, 2)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


TECH_ACTIVITIES = (
    "пахота",
    "чизелевание",
    "дискование",
    "культивация сплошная",
    "культивация междурядная",
    "опрыскивание",
    "комбайн уборка",
    "сев",
    "боронование",
)
MANUAL_ACTIVITIES = ("прополка", "сбор", "полив", "монтаж", "ремонт", "прочее")


def kb_tech_activities() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=a, callback_data=f"act:{a}") for a in TECH_ACTIVITIES]
    ik = rows(btns, 2)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


def kb_manual_activities() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=a, callback_data=f"act:{a}") for a in MANUAL_ACTIVITIES]
    ik = rows(btns, 2)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


def kb_activity_for(wtype: str) -> InlineKeyboardMarkup:
    return kb_tech_activities() if wtype == "техника" else kb_manual_activities()


def kb_location_group() -> InlineKeyboardMarkup:
    btns = [
        [
            InlineKeyboardButton(text="поля", callback_data="locgrp:поля"),
            InlineKeyboardButton(text="склад", callback_data="locgrp:склад"),
        ],
        *kb_back_cancel().inline_keyboard,
    ]
    return InlineKeyboardMarkup(inline_keyboard=btns)


def kb_location_fields() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=name, callback_data=f"field:{name}") for name in FIELDS]
    ik = rows(btns, 2)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


def human_date_label(d: date, today: date) -> str:
    if d == today:
        return f"Сегодня ({d.strftime('%d.%m')})"
    if d == today - timedelta(days=1):
        return f"Вчера ({d.strftime('%d.%m')})"
    if d == today + timedelta(days=1):
        return f"Завтра ({d.strftime('%d.%m')})"
    return d.strftime("%d.%m (%a)")


def kb_dates() -> InlineKeyboardMarkup:
    today = datetime.now(TZ).date()
    choices = [today + timedelta(days=o) for o in (-2, -1, 0, 1, 2)]
    btns = [InlineKeyboardButton(text=human_date_label(d, today), callback_data=f"date:{d.isoformat()}") for d in choices]
    ik = rows(btns, 1)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


def kb_hours() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=str(i), callback_data=f"hrs:{i}") for i in range(1, 25)]
    ik = rows(btns, 6)
    ik += kb_back_cancel().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=ik)


# ---------------- FSM ----------------
class ReportStates(StatesGroup):
    awaiting_full_name = State()

    choosing_work_type = State()
    choosing_activity = State()
    waiting_activity_text = State()

    choosing_location_group = State()
    choosing_location = State()

    choosing_date = State()
    choosing_hours = State()


# ---------------- Меню / регистрация ----------------
async def show_menu(message: Message, reg: str):
    await message.answer(
        f"Привет! Вы зарегистрированы как: *{reg}*\nВыберите действие:",
        reply_markup=main_menu_kb(is_admin_user(message.from_user.id, message.from_user.username, CFG)),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    reg = get_registered_name(message.from_user.id)
    if not reg:
        await state.set_state(ReportStates.awaiting_full_name)
        await message.answer(
            "👋 Для начала укажите *Фамилию и Имя* (свободная форма):",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await show_menu(message, reg)


async def cmd_register(message: Message, state: FSMContext):
    await state.set_state(ReportStates.awaiting_full_name)
    await message.answer("Введите *Фамилию и Имя* заново:", parse_mode=ParseMode.MARKDOWN)


async def capture_full_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Слишком коротко. Укажите *Фамилию и Имя* полностью.", parse_mode=ParseMode.MARKDOWN)
        return
    upsert_user(message.from_user.id, text, TZ, message.from_user.username)
    await message.answer(f"Готово! Вы зарегистрированы как: *{text}*.", parse_mode=ParseMode.MARKDOWN)
    await show_menu(message, text)
    await state.clear()


async def menu_click(call: CallbackQuery, state: FSMContext):
    await call.answer()  # не висим
    data = call.data.split(":", 1)[1]
    reg = get_registered_name(call.from_user.id) or "(не зарегистрирован)"
    if data == "work":
        await state.set_state(ReportStates.choosing_work_type)
        await call.message.edit_text("Выберите *виды работ*:", reply_markup=kb_work_types(), parse_mode=ParseMode.MARKDOWN)
    elif data == "stats":
        await call.message.edit_text("Статистика:", reply_markup=kb_stats_menu())


# ---------------- Статистика ----------------
async def show_stats(message: Message, tz: ZoneInfo, for_user_id: Optional[int], period: str, as_admin: bool):
    today = datetime.now(tz).date()
    if period == "today":
        start = end = today
        title = "за сегодня"
    else:
        start = today - timedelta(days=6)
        end = today
        title = "за неделю"

    rows = fetch_reports_between(start, end, for_user_id=None if as_admin else for_user_id)
    if not rows:
        scope = "всех" if as_admin else "ваши"
        await message.answer(f"Записей {title} ({scope}) нет.")
        return

    total = sum(r[5] for r in rows)
    lines = [f"<b>Статистика {title}:</b> всего часов: <b>{total}</b>"]
    for i, (wd, reg, uname, loc, act, hrs) in enumerate(rows[:20], 1):
        who = reg or (f"@{uname}" if uname else "-")
        lines.append(f"{i}. {wd} • {who} • {loc} • {act} — <b>{hrs}</b> ч")
    if len(rows) > 20:
        lines.append(f"... и ещё {len(rows)-20} записей")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_today(message: Message):
    await show_stats(
        message=message,
        tz=TZ,
        for_user_id=message.from_user.id,
        period="today",
        as_admin=is_admin_user(message.from_user.id, message.from_user.username, CFG),
    )


async def cmd_my(message: Message):
    await show_stats(
        message=message,
        tz=TZ,
        for_user_id=message.from_user.id,
        period="week",
        as_admin=False,
    )


async def stats_click(call: CallbackQuery, state: FSMContext):
    """Обработка кнопок 'Сегодня' / 'Неделя' из меню статистики."""
    await call.answer()  # сразу отвечаем, чтобы не висело
    what = call.data.split(":", 1)[1]
    is_admin = is_admin_user(call.from_user.id, call.from_user.username, CFG)
    if what == "today":
        await show_stats(call.message, TZ, call.from_user.id, "today", is_admin)
    else:
        await show_stats(call.message, TZ, call.from_user.id, "week", is_admin)


# ---------------- Рабочий поток ----------------
async def handle_work_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    wtype = call.data.split(":", 1)[1]
    await state.update_data(work_type=wtype)
    if wtype == "техника":
        await call.message.edit_text("Техника → выберите вид работы:", reply_markup=kb_tech_activities())
    else:
        await call.message.edit_text("Ручная → выберите вид работы:", reply_markup=kb_manual_activities())
    await state.set_state(ReportStates.choosing_activity)


async def handle_activity(call: CallbackQuery, state: FSMContext):
    await call.answer()
    act = call.data.split(":", 1)[1]
    if act == "прочее":
        await state.set_state(ReportStates.waiting_activity_text)
        await call.message.edit_text("Укажите название работы (произвольный текст):")
        return
    await state.update_data(activity=act)
    await call.message.edit_text(
        f"Работа: <b>{act}</b>\nТеперь выберите *место работы*: 'поля' или 'склад'.",
        reply_markup=kb_location_group(),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(ReportStates.choosing_location_group)


async def capture_custom_activity(message: Message, state: FSMContext):
    act = (message.text or "").strip()
    if not act:
        await message.answer("Пустое название, введите ещё раз:")
        return
    await state.update_data(activity=act)
    await message.answer(
        f"Работа: <b>{act}</b>\nТеперь выберите *место работы*: 'поля' или 'склад'.",
        reply_markup=kb_location_group(),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(ReportStates.choosing_location_group)


async def on_loc_group(c: CallbackQuery, state: FSMContext):
    await c.answer()
    grp = c.data.split(":", 1)[1]  # "поля" или "склад"
    await state.update_data(loc_group=grp)
    if grp == "склад":
        await state.update_data(location="склад")
        await state.set_state(ReportStates.choosing_date)
        await c.message.edit_text("Дата: выберите число (±2 дня):", reply_markup=kb_dates())
    else:
        await state.set_state(ReportStates.choosing_location)
        await c.message.edit_text("Выберите локацию (поле):", reply_markup=kb_location_fields())


async def on_field(c: CallbackQuery, state: FSMContext):
    await c.answer()
    name = c.data.split(":", 1)[1]
    await state.update_data(location=name)
    await state.set_state(ReportStates.choosing_date)
    await c.message.edit_text("Дата: выберите число (±2 дня):", reply_markup=kb_dates())


async def handle_location(call: CallbackQuery, state: FSMContext):
    # (не используется в новой логике; оставлено на случай совместимости)
    await call.answer()


async def handle_date(call: CallbackQuery, state: FSMContext):
    await call.answer()
    d = call.data.split(":", 1)[1]
    await state.update_data(work_date=d)
    await call.message.edit_text(
        f"Дата: <b>{d}</b>\nСколько часов отработано?",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_hours(),
    )
    await state.set_state(ReportStates.choosing_hours)


async def handle_hours(call: CallbackQuery, state: FSMContext):
    await call.answer()
    hrs = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    created_at = datetime.now(TZ).isoformat(timespec="seconds")
    full_name = get_registered_name(call.from_user.id) or ""
    username = call.from_user.username
    insert_report(
        created_at=created_at,
        user_id=call.from_user.id,
        full_name=full_name,
        username=username,
        location=data["location"],
        activity=data["activity"],
        work_date=data["work_date"],
        hours=hrs,
        chat_id=call.message.chat.id,
    )
    await call.message.edit_text(
        "✅ Запись сохранена\n\n"
        f"Работник: {full_name or ('@'+(username or ''))}\n"
        f"Место: {data.get('loc_group', '-')}; {data['location']}\n"
        f"Работа: {data['activity']}\n"
        f"Дата: {data['work_date']}\n"
        f"Часы: {hrs}",
    )
    await state.clear()


# ---------------- Назад / Отмена ----------------
async def on_back(call: CallbackQuery, state: FSMContext):
    await call.answer()
    st = await state.get_state()
    data = await state.get_data()

    if st == ReportStates.choosing_work_type.state:
        reg = get_registered_name(call.from_user.id) or "(не зарегистрирован)"
        await call.message.edit_text("Главное меню:", reply_markup=main_menu_kb(is_admin_user(call.from_user.id, call.from_user.username, CFG)))
        await state.clear()
        return

    if st == ReportStates.choosing_activity.state:
        await call.message.edit_text("Выберите *виды работ*:", reply_markup=kb_work_types(), parse_mode=ParseMode.MARKDOWN)
        await state.set_state(ReportStates.choosing_work_type)
        return

    if st == ReportStates.waiting_activity_text.state:
        await call.message.edit_text("Выберите вид работы (ручная):", reply_markup=kb_manual_activities())
        await state.set_state(ReportStates.choosing_activity)
        return

    if st == ReportStates.choosing_location_group.state:
        # назад к выбору активности (с учётом типа работ)
        wtype = data.get("work_type", "ручная")
        await call.message.edit_text(
            "Выберите вид работы:",
            reply_markup=kb_activity_for(wtype),
        )
        await state.set_state(ReportStates.choosing_activity)
        return

    if st == ReportStates.choosing_location.state:
        await call.message.edit_text("Выберите *место работы*:", reply_markup=kb_location_group())
        await state.set_state(ReportStates.choosing_location_group)
        return

    if st == ReportStates.choosing_date.state:
        # если был выбран путь через "поля" → вернём список полей, иначе к выбору группы
        if data.get("loc_group") == "поля":
            await call.message.edit_text("Выберите локацию (поле):", reply_markup=kb_location_fields())
            await state.set_state(ReportStates.choosing_location)
        else:
            await call.message.edit_text("Выберите *место работы*:", reply_markup=kb_location_group())
            await state.set_state(ReportStates.choosing_location_group)
        return

    if st == ReportStates.choosing_hours.state:
        await call.message.edit_text("Дата: выберите число (±2 дня):", reply_markup=kb_dates())
        await state.set_state(ReportStates.choosing_date)
        return

    await call.message.answer("Назад недоступен.")


async def on_cancel(call: CallbackQuery, state: FSMContext):
    await call.answer("Отменено")
    await state.clear()
    reg = get_registered_name(call.from_user.id) or "(не зарегистрирован)"
    await call.message.edit_text("Главное меню:", reply_markup=main_menu_kb(is_admin_user(call.from_user.id, call.from_user.username, CFG)))


# ---------------- Экспорт CSV ----------------
def export_month_csv(yyyymm: str) -> Path:
    year, month = map(int, yyyymm.split("-"))
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1)

    out = Path(f"reports_{yyyymm}.csv")
    with sqlite3.connect(DB_PATH) as conn, out.open("w", newline="", encoding="utf-8") as f:
        c = conn.cursor()
        c.execute(
            """
            SELECT created_at, user_id, full_name, username, location, activity, work_date, hours, chat_id
            FROM reports
            WHERE date(work_date) >= date(?) AND date(work_date) < date(?)
            ORDER BY work_date ASC, created_at ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        writer = csv.writer(f)
        writer.writerow(["created_at","user_id","full_name","username","location","activity","work_date","hours","chat_id"])
        for row in c.fetchall():
            writer.writerow(row)
    return out


async def cmd_export(message: Message, command: CommandObject):
    if not is_admin_user(message.from_user.id, message.from_user.username, CFG):
        await message.answer("Команда доступна только админам.")
        return

    now = datetime.now(TZ)
    if command.args:
        yyyymm = command.args.strip()
        try:
            datetime.strptime(yyyymm, "%Y-%m")
        except ValueError:
            await message.answer("Неверный формат. Используйте /export YYYY-MM, например /export 2025-08")
            return
    else:
        yyyymm = now.strftime("%Y-%m")

    path = export_month_csv(yyyymm)
    if path.exists():
        await message.answer_document(document=path.open("rb"), caption=f"Экспорт {yyyymm}")
    else:
        await message.answer("Данных за указанный месяц нет.")


# ---------------- Excel + Google Drive ----------------
def export_month_xlsx_local(yyyymm: str) -> Path:
    from openpyxl import Workbook

    year, month = map(int, yyyymm.split("-"))
    start = date(year, month, 1)
    end = (date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1))

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT COALESCE(full_name, ''), activity, location, work_date, hours
            FROM reports
            WHERE date(work_date) >= date(?) AND date(work_date) <= date(?)
            ORDER BY work_date ASC, created_at ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        rows = c.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёт"
    ws.append(["Фамилия Имя", "Виды работ", "Место работы", "Дата", "Кол-во часов"])
    for r in rows:
        ws.append(list(r))

    out = Path(f"Reports-{yyyymm}.xlsx")
    wb.save(out)
    return out


def drive_upload_month_xlsx(cfg: Config, yyyymm: str, local_file: Path) -> Optional[str]:
    if not cfg.sa_json or not cfg.drive_folder_id:
        print("[export] Drive creds/folder not set; skip upload")
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception as e:
        print("[export] Google packages missing:", e)
        return None

    scopes = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(cfg.sa_json, scopes=scopes)
    drive = build("drive", "v3", credentials=creds)

    name = f"Reports-{yyyymm}.xlsx"
    query = f"name = '{name}' and '{cfg.drive_folder_id}' in parents and trashed = false"
    res = drive.files().list(q=query, fields="files(id, name)").execute()
    items = res.get("files", [])

    media = MediaFileUpload(
        str(local_file),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=False,
    )

    if items:
        file_id = items[0]["id"]
        drive.files().update(fileId=file_id, media_body=media).execute()
        print(f"[export] Updated Drive file: {name} ({file_id})")
        return file_id
    else:
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "parents": [cfg.drive_folder_id],
        }
        created = drive.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"[export] Created Drive file: {name} ({created.get('id')})")
        return created.get("id")


async def auto_export_loop(cfg: Config, tz: ZoneInfo):
    while True:
        now = datetime.now(tz)
        target_dt = datetime.combine(now.date(), time(23, 59, 0, tzinfo=tz))
        if now >= target_dt:
            target_dt += timedelta(days=1)
        sleep_s = (target_dt - now).total_seconds()
        print(f"[export] next run at {target_dt.isoformat()} (in {int(sleep_s)}s)")
        try:
            await asyncio.sleep(sleep_s)
        except asyncio.CancelledError:
            return
        try:
            yyyymm = datetime.now(tz).strftime("%Y-%m")
            xlsx = export_month_xlsx_local(yyyymm)
            drive_upload_month_xlsx(cfg, yyyymm, xlsx)
        except Exception as e:
            print("[export] error:", e)


# ---------------- Прочее ----------------
async def cmd_version(message: Message):
    await message.answer(f"Version: {APP_VERSION}\nFile: {__file__}")


# ---------------- Регистрация хендлеров ----------------
def register_handlers() -> None:
    # команды
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_register, Command("register"))
    dp.message.register(cmd_today, Command("today"))
    dp.message.register(cmd_my, Command("my"))
    dp.message.register(cmd_export, Command("export"))
    dp.message.register(cmd_version, Command("version"))
    dp.message.register(capture_full_name, ReportStates.awaiting_full_name)

    # меню
    dp.callback_query.register(menu_click, F.data.startswith("menu:"))
    dp.callback_query.register(stats_click, F.data.startswith("stats:"))
    dp.callback_query.register(stat_today_cq, F.data == "stat:today")

    # админ функции
    dp.callback_query.register(open_admin, F.data == "menu:admin")
    dp.callback_query.register(adm_del_loc, F.data == "adm:del_loc")
    dp.callback_query.register(_del_loc, F.data.startswith("del_loc:"))
    dp.callback_query.register(adm_del_act, F.data == "adm:del_act")
    dp.callback_query.register(_del_act, F.data.startswith("del_act:"))
    dp.callback_query.register(adm_add_loc, F.data == "adm:add_loc")
    dp.callback_query.register(adm_add_loc_kind, F.data.startswith("adm:add_loc_kind:"))
    dp.callback_query.register(adm_add_act_tech, F.data == "adm:add_act_tech")
    dp.callback_query.register(adm_add_act_manual, F.data == "adm:add_act_manual")

    # поток отчёта
    dp.callback_query.register(handle_work_type, F.data.startswith("wtype:"))
    dp.callback_query.register(handle_activity, F.data.startswith("act:"))
    dp.message.register(capture_custom_activity, ReportStates.waiting_activity_text)

    dp.callback_query.register(on_loc_group, F.data.startswith("locgrp:"))
    dp.callback_query.register(on_field, F.data.startswith("field:"))

    dp.callback_query.register(handle_date, F.data.startswith("date:"))
    dp.callback_query.register(handle_hours, F.data.startswith("hrs:"))

    # управление
    dp.callback_query.register(on_back, F.data.startswith("back:"))
    dp.callback_query.register(on_cancel, F.data == "cancel")


# ---------------- Main ----------------
async def main():
    global CFG, TZ
    print("[main] enter")

    CFG = load_config()
    TZ = ZoneInfo(CFG.tz)

    init_db()
    print("[main] db initialized")

    register_handlers()

    bot = Bot(CFG.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("[main] bot created; Bot is running...")

    asyncio.create_task(auto_export_loop(CFG, TZ))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
