from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, cast
from sqlalchemy.types import Date as DateColumn
from datetime import date
import os
from app.core.database import get_db
from app.models.report import Report, BrigadierReport, FormResponse
from app.models.user import User
from app.api.deps import require_accountant_or_admin, require_admin
from app.services.excel_export import build_otd_excel, build_accounting_excel


def _parse_hours(data: dict) -> float:
    """Extract numeric hours from form_response JSON data."""
    if not data:
        return 0.0
    for k in ("hours", "часы"):
        v = data.get(k)
        if v not in (None, ""):
            try:
                return float(str(v).replace(",", "."))
            except (ValueError, TypeError):
                pass
    return 0.0

router = APIRouter(prefix="/export", tags=["export"])

EXPORT_DIR = "/tmp/terra_exports"
os.makedirs(EXPORT_DIR, exist_ok=True)


@router.post("/excel/otd")
async def export_otd_excel(
    date_from: date,
    date_to: date,
    background_tasks: BackgroundTasks,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(
            and_(Report.work_date >= date_from, Report.work_date <= date_to)
        ).order_by(Report.work_date, Report.user_id)
    )
    reports = result.scalars().all()

    filepath = os.path.join(EXPORT_DIR, f"otd_{date_from}_{date_to}.xlsx")
    await build_otd_excel(reports, filepath)

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"ОТД_{date_from}_{date_to}.xlsx",
    )


@router.post("/excel/accounting")
async def export_accounting_excel(
    date_from: date,
    date_to: date,
    admin=Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report, User).join(User, Report.user_id == User.id, isouter=True).where(
            and_(Report.work_date >= date_from, Report.work_date <= date_to)
        ).order_by(Report.user_id, Report.work_date)
    )
    rows = result.all()

    filepath = os.path.join(EXPORT_DIR, f"accounting_{date_from}_{date_to}.xlsx")
    await build_accounting_excel(rows, date_from, date_to, filepath)

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"ЗП-ОТД_{date_from}_{date_to}.xlsx",
    )


def _work_date_filters(model, date_from: date | None, date_to: date | None):
    conds = []
    if date_from is not None:
        conds.append(model.work_date >= date_from)
    if date_to is not None:
        conds.append(model.work_date <= date_to)
    return and_(*conds) if conds else None


def _submitted_at_filters(date_from: date | None, date_to: date | None):
    conds = []
    if date_from is not None:
        conds.append(cast(FormResponse.submitted_at, DateColumn) >= date_from)
    if date_to is not None:
        conds.append(cast(FormResponse.submitted_at, DateColumn) <= date_to)
    return and_(*conds) if conds else None


@router.get("/stats/admin")
async def admin_stats(
    date_from: date | None = None,
    date_to: date | None = None,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Сводка по сотрудникам за период.
    Часы — только ОТД (reports). Счётчик «отчётов» — ОТД + бригадир + динамические формы
    (как в мобильной /api/v1/stats).
    Фильтры по датам применяются внутри подзапросов, чтобы пользователи без ОТД за период
    не исчезали из выборки, если у них есть другие типы отчётов.
    """
    otd_where = _work_date_filters(Report, date_from, date_to)
    otd_stmt = (
        select(
            Report.user_id.label("uid"),
            func.coalesce(func.sum(Report.hours), 0).label("total_hours"),
            func.count(Report.id).label("otd_count"),
        )
        .group_by(Report.user_id)
    )
    if otd_where is not None:
        otd_stmt = otd_stmt.where(otd_where)
    otd_sq = otd_stmt.subquery()

    brig_where = _work_date_filters(BrigadierReport, date_from, date_to)
    brig_stmt = select(BrigadierReport.user_id.label("uid"), func.count(BrigadierReport.id).label("brig_count")).group_by(
        BrigadierReport.user_id
    )
    if brig_where is not None:
        brig_stmt = brig_stmt.where(brig_where)
    brig_sq = brig_stmt.subquery()

    fr_where = _submitted_at_filters(date_from, date_to)
    form_stmt = select(FormResponse.user_id.label("uid"), func.count(FormResponse.id).label("form_count")).group_by(
        FormResponse.user_id
    )
    if fr_where is not None:
        form_stmt = form_stmt.where(fr_where)
    form_sq = form_stmt.subquery()

    q = (
        select(
            User.id,
            User.full_name,
            func.coalesce(otd_sq.c.total_hours, 0).label("total_hours"),
            (
                func.coalesce(otd_sq.c.otd_count, 0)
                + func.coalesce(brig_sq.c.brig_count, 0)
                + func.coalesce(form_sq.c.form_count, 0)
            ).label("report_count"),
        )
        .select_from(User)
        .outerjoin(otd_sq, User.id == otd_sq.c.uid)
        .outerjoin(brig_sq, User.id == brig_sq.c.uid)
        .outerjoin(form_sq, User.id == form_sq.c.uid)
        .order_by(func.coalesce(otd_sq.c.total_hours, 0).desc().nullslast())
    )

    result = await db.execute(q)
    rows = result.all()

    # Sum hours from form_responses (stored as JSON strings)
    fr_all_q = select(FormResponse.user_id, FormResponse.data)
    if fr_where is not None:
        fr_all_q = fr_all_q.where(fr_where)
    fr_all = (await db.execute(fr_all_q)).all()
    form_hours_by_user: dict[int, float] = {}
    for uid, data in fr_all:
        h = _parse_hours(data or {})
        if h > 0:
            form_hours_by_user[uid] = form_hours_by_user.get(uid, 0.0) + h

    return [
        {
            "user_id": r.id,
            "full_name": r.full_name,
            "total_hours": float(r.total_hours or 0) + form_hours_by_user.get(r.id, 0.0),
            "report_count": int(r.report_count or 0),
        }
        for r in rows
    ]
