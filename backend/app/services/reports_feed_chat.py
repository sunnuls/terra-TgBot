"""Публикация отчётов в общий чат «Отчётность» (как лента в Telegram)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.realtime.chat_hub import broadcast_chat_message, push_offline_room_members
from app.core.database import AsyncSessionLocal
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.models.form import FormTemplate
from app.models.report import BrigadierReport, FormResponse, Report
from app.models.tenant import TenantSettings
from app.models.user import User

logger = logging.getLogger(__name__)

REPORTS_FEED_NAME = "Отчётность"


def _fmt_line(label: str, value: str | None) -> str:
    if value is None or value == "":
        return f"{label}: —"
    return f"{label}: {value}"


def format_classic_otd_message(r: Report, *, edited: bool = False, old_snapshot: dict | None = None) -> str:
    name = r.reg_name or r.username or "—"
    header = "✏️ Изменено (ОТД)" if edited else "✅ Новая запись (ОТД)"
    lines = [
        header,
        "",
        name,
        f"📅 {r.work_date}" if r.work_date else "📅 —",
        f"📍 {r.location or '—'}",
        f"🚜 {r.activity or '—'} ({r.activity_grp or '—'})",
    ]
    tech = (r.machine_type or "") + (f" — {r.machine_name}" if r.machine_name else "")
    lines.append(_fmt_line("Техника", tech.strip() or None))
    lines.append(_fmt_line("Культура", r.crop))
    lines.append(f"⏱ {r.hours} ч" if r.hours is not None else "⏱ —")
    lines.append(f"ID: #OTD-{r.id}")

    if edited and old_snapshot:
        checks = [
            ("📅 Дата",       "work_date",   str(r.work_date) if r.work_date else ""),
            ("📍 Место",      "location",    r.location or ""),
            ("🚜 Деятельность", "activity",  r.activity or ""),
            ("Тип работ",     "activity_grp", r.activity_grp or ""),
            ("Техника",       "machine_type", r.machine_type or ""),
            ("Культура",      "crop",         r.crop or ""),
            ("⏱ Часов",      "hours",        str(r.hours) if r.hours is not None else ""),
        ]
        diff = []
        for label, snap_key, new_val in checks:
            old_val = str(old_snapshot.get(snap_key) or "").strip()
            nv = new_val.strip()
            if old_val != nv and (old_val or nv):
                diff.append(f"{label}: {old_val or '—'} → {nv or '—'}")
        if diff:
            lines.append("Изменения:")
            lines.extend(diff)

    return "\n".join(lines)


def _extract_field(data: dict, named_key: str, flow_sources: list[str], flow: dict | None) -> str | None:
    """Ищет значение поля: сначала по именованному ключу, потом по source в flow-нодах."""
    if named_key in data and data[named_key]:
        return str(data[named_key])
    if flow and flow_sources:
        for node in flow.get("nodes", []):
            src = node.get("source") or ""
            if any(s in src for s in flow_sources) and node["id"] in data and data[node["id"]]:
                return str(data[node["id"]])
    return None


def _extract_all_fields(d: dict, flow: dict | None) -> dict:
    """Extract the key display fields from a form data dict."""
    wd = _extract_field(d, "work_date", [], None) or _extract_field(d, "date", ["date"], flow) or ""
    loc = _extract_field(d, "location", ["locations", "locations_field", "locations_store"], flow) or ""
    wt = (d.get("work_type") or "").strip()
    if "Техника" in wt or (d.get("activity_tech") and not d.get("activity_hand")):
        act = _extract_field(d, "activity_tech", ["activities_tech"], flow) or ""
        grp = "техника"
    else:
        act = _extract_field(d, "activity_hand", ["activities_hand"], flow) or ""
        grp = "ручная"
    tech = _extract_field(d, "machine_type", ["machine_kinds"], flow) or ""
    crop = _extract_field(d, "crop", ["crops"], flow) or ""
    hrs = str(d.get("hours") or "")
    return {"wd": wd, "loc": loc, "act": act, "grp": grp, "tech": tech, "crop": crop, "hrs": hrs, "wt": wt}


def _build_diff_lines(old: dict, new: dict, flow: dict | None) -> list[str]:
    """Compare extracted fields between old and new data, return '→' change lines."""
    of = _extract_all_fields(old, flow)
    nf = _extract_all_fields(new, flow)
    checks = [
        ("📅 Дата",       "wd"),
        ("📍 Место",      "loc"),
        ("Тип работ",     "wt"),
        ("🚜 Деятельность", "act"),
        ("Техника",       "tech"),
        ("Культура",      "crop"),
        ("⏱ Часов",      "hrs"),
    ]
    lines = []
    for label, key in checks:
        ov = of[key].strip()
        nv = nf[key].strip()
        if ov != nv and (ov or nv):
            lines.append(f"{label}: {ov or '—'} → {nv or '—'}")
    return lines


def format_form_otd_message(data: dict, name: str, response_id: int, *, edited: bool = False, flow: dict | None = None, old_data: dict | None = None) -> str:
    d = data or {}
    header = "✏️ Изменено (форма ОТД)" if edited else "✅ Новая запись (форма ОТД)"

    f = _extract_all_fields(d, flow)

    lines = [
        header,
        "",
        name,
        f"📅 {f['wd'] or '—'}",
        f"📍 {f['loc'] or '—'}",
        f"🚜 {f['act'] or '—'} ({f['grp']})",
        _fmt_line("Техника", f["tech"] or None),
        _fmt_line("Культура", f["crop"] or None),
        f"⏱ {f['hrs']} ч" if f["hrs"] else "⏱ —",
        f"ID: #FORM-{response_id}",
    ]

    if edited and old_data is not None:
        diff = _build_diff_lines(old_data, d, flow)
        if diff:
            lines.append("Изменения:")
            lines.extend(diff)

    return "\n".join(lines)


def format_brig_message(r: BrigadierReport, *, edited: bool = False) -> str:
    name = r.username or "—"
    header = "✏️ Изменено (бригадир)" if edited else "✅ Отчёт бригадира"
    lines = [
        header,
        "",
        name,
        f"📅 {r.work_date or '—'}",
        f"📍 {r.field or '—'}",
        f"🔧 {r.work_type or '—'}",
        f"👷 {r.workers} чел." if r.workers is not None else "👷 —",
        f"Смена: {r.shift or '—'}",
        f"ID: #BRIG-{r.id}",
    ]
    return "\n".join(lines)


async def get_or_create_reports_feed_room(db: AsyncSession) -> int | None:
    ts = (await db.execute(select(TenantSettings).where(TenantSettings.id == 1))).scalar_one_or_none()
    if not ts:
        logger.warning("tenant_settings id=1 missing")
        return None

    if ts.reports_feed_room_id:
        chk = await db.execute(select(ChatRoom.id).where(ChatRoom.id == ts.reports_feed_room_id))
        if chk.scalar_one_or_none():
            return ts.reports_feed_room_id

    existing = await db.execute(
        select(ChatRoom).where(ChatRoom.name == REPORTS_FEED_NAME, ChatRoom.type == "group")
    )
    ex = existing.scalar_one_or_none()
    if ex:
        ts.reports_feed_room_id = ex.id
        await db.commit()
        return ex.id

    first_u = await db.execute(select(User.id).where(User.is_active == True).order_by(User.id.asc()).limit(1))
    creator = first_u.scalar_one_or_none()
    if not creator:
        return None

    room = ChatRoom(name=REPORTS_FEED_NAME, type="group", created_by=creator)
    db.add(room)
    await db.flush()

    users_res = await db.execute(select(User.id).where(User.is_active == True))
    for (uid,) in users_res.all():
        db.add(ChatRoomMember(room_id=room.id, user_id=uid))

    ts.reports_feed_room_id = room.id
    await db.commit()
    await db.refresh(room)
    return room.id


async def post_feed_message(db: AsyncSession, room_id: int, sender_id: int, content: str) -> None:
    msg = ChatMessage(room_id=room_id, sender_id=sender_id, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    user = await db.get(User, sender_id)
    sender_name = user.full_name if user else None
    await broadcast_chat_message(room_id, msg, sender_name)
    await push_offline_room_members(
        room_id,
        sender_id,
        title=sender_name or "TerraApp",
        body=content,
        db=db,
    )


async def announce_classic_otd(report_id: int, sender_id: int) -> None:
    try:
        async with AsyncSessionLocal() as db:
            report = await db.get(Report, report_id)
            if not report:
                return
            text = format_classic_otd_message(report)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_classic_otd failed report_id=%s", report_id)


async def announce_classic_otd_edit(report_id: int, sender_id: int, old_snapshot: dict | None = None) -> None:
    try:
        async with AsyncSessionLocal() as db:
            report = await db.get(Report, report_id)
            if not report:
                return
            text = format_classic_otd_message(report, edited=True, old_snapshot=old_snapshot)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_classic_otd_edit failed report_id=%s", report_id)


async def _get_flow_for_form(ft: FormTemplate) -> dict | None:
    """Безопасно извлекает flow из схемы шаблона формы."""
    try:
        schema = ft.schema if isinstance(ft.schema, dict) else {}
        return schema.get("flow")
    except Exception:
        return None


async def announce_form_otd(response_id: int, sender_id: int) -> None:
    try:
        async with AsyncSessionLocal() as db:
            fr = await db.get(FormResponse, response_id)
            if not fr:
                return
            ft = await db.get(FormTemplate, fr.form_id)
            if not ft or ft.name != "otd":
                return
            user = await db.get(User, sender_id)
            name = user.full_name if user else f"#{sender_id}"
            flow = await _get_flow_for_form(ft)
            text = format_form_otd_message(fr.data or {}, name, response_id, flow=flow)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_form_otd failed response_id=%s", response_id)


async def announce_form_otd_edit(response_id: int, sender_id: int, old_data: dict | None = None) -> None:
    try:
        async with AsyncSessionLocal() as db:
            fr = await db.get(FormResponse, response_id)
            if not fr:
                return
            ft = await db.get(FormTemplate, fr.form_id)
            if not ft or ft.name != "otd":
                return
            user = await db.get(User, sender_id)
            name = user.full_name if user else f"#{sender_id}"
            flow = await _get_flow_for_form(ft)
            text = format_form_otd_message(fr.data or {}, name, response_id, edited=True, flow=flow, old_data=old_data)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_form_otd_edit failed response_id=%s", response_id)


async def announce_brig(report_id: int, sender_id: int) -> None:
    try:
        async with AsyncSessionLocal() as db:
            r = await db.get(BrigadierReport, report_id)
            if not r:
                return
            text = format_brig_message(r)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_brig failed report_id=%s", report_id)


async def announce_classic_otd_delete(report_id: int, sender_id: int, snapshot: dict) -> None:
    """snapshot — данные отчёта до удаления (dict с полями)"""
    try:
        async with AsyncSessionLocal() as db:
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            name = snapshot.get("reg_name") or "—"
            lines = [
                "🗑️ Удалена запись (ОТД)",
                "",
                name,
                f"📅 {snapshot.get('work_date') or '—'}",
                f"📍 {snapshot.get('location') or '—'}",
                f"🚜 {snapshot.get('activity') or '—'} ({snapshot.get('activity_grp') or '—'})",
                f"⏱ {snapshot.get('hours')} ч" if snapshot.get('hours') is not None else "⏱ —",
                f"ID: #OTD-{report_id}",
            ]
            await post_feed_message(db, room_id, sender_id, "\n".join(lines))
    except Exception:
        logger.exception("announce_classic_otd_delete failed report_id=%s", report_id)


async def announce_form_otd_delete(response_id: int, sender_id: int, snapshot: dict, name: str, form_id: int | None = None) -> None:
    """snapshot — данные FormResponse.data до удаления"""
    try:
        async with AsyncSessionLocal() as db:
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            flow = None
            if form_id:
                ft = await db.get(FormTemplate, form_id)
                if ft:
                    flow = await _get_flow_for_form(ft)
            text = format_form_otd_message(snapshot, name, response_id, flow=flow)
            text = text.replace("✅ Новая запись (форма ОТД)", "🗑️ Удалена запись (форма ОТД)")
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_form_otd_delete failed response_id=%s", response_id)


async def announce_brig_delete(report_id: int, sender_id: int, snapshot: dict) -> None:
    try:
        async with AsyncSessionLocal() as db:
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            lines = [
                "🗑️ Удалён отчёт бригадира",
                "",
                snapshot.get("username") or "—",
                f"📅 {snapshot.get('work_date') or '—'}",
                f"📍 {snapshot.get('field') or '—'}",
                f"🔧 {snapshot.get('work_type') or '—'}",
                f"👷 {snapshot.get('workers')} чел." if snapshot.get('workers') is not None else "👷 —",
                f"ID: #BRIG-{report_id}",
            ]
            await post_feed_message(db, room_id, sender_id, "\n".join(lines))
    except Exception:
        logger.exception("announce_brig_delete failed report_id=%s", report_id)


async def announce_brig_edit(report_id: int, sender_id: int) -> None:
    try:
        async with AsyncSessionLocal() as db:
            r = await db.get(BrigadierReport, report_id)
            if not r:
                return
            text = format_brig_message(r, edited=True)
            room_id = await get_or_create_reports_feed_room(db)
            if not room_id:
                return
            await post_feed_message(db, room_id, sender_id, text)
    except Exception:
        logger.exception("announce_brig_edit failed report_id=%s", report_id)


async def add_user_to_reports_feed_if_exists(db: AsyncSession, user_id: int) -> None:
    """Вызывать после регистрации: добавить в «Отчётность», если комната уже есть."""
    try:
        ts = (await db.execute(select(TenantSettings).where(TenantSettings.id == 1))).scalar_one_or_none()
        if not ts or not ts.reports_feed_room_id:
            return
        rid = ts.reports_feed_room_id
        exists = await db.execute(
            select(ChatRoomMember).where(
                ChatRoomMember.room_id == rid, ChatRoomMember.user_id == user_id
            )
        )
        if exists.scalar_one_or_none():
            return
        db.add(ChatRoomMember(room_id=rid, user_id=user_id))
        await db.commit()
    except Exception:
        logger.exception("add_user_to_reports_feed_if_exists user_id=%s", user_id)
