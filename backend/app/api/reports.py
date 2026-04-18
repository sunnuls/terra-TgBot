from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select, func, and_, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date as DateColumn

from app.api.deps import (
    get_current_user,
    get_current_user_role,
    require_accountant_or_admin,
)
from app.core.database import get_db
from app.models.form import FormTemplate
from app.models.report import Report, BrigadierReport, FormResponse
from app.models.user import User, UserRole
from app.services.reports_feed_chat import (
    announce_brig,
    announce_brig_delete,
    announce_brig_edit,
    announce_classic_otd,
    announce_classic_otd_delete,
    announce_classic_otd_edit,
    announce_form_otd,
    announce_form_otd_delete,
    announce_form_otd_edit,
)
from app.schemas.report import (
    BrigReportCreate,
    BrigReportOut,
    BrigReportUpdate,
    FormResponseCreate,
    FormResponseOut,
    ReportCreate,
    ReportFeedItemOut,
    ReportOut,
    ReportUpdate,
    StatsOut,
)

router = APIRouter(tags=["reports"])


def _parse_hours_from_form_data(data: dict) -> float:
    if not data:
        return 0.0
    for k in ("hours", "часы"):
        if k in data and data[k] not in (None, ""):
            try:
                return float(str(data[k]).replace(",", "."))
            except ValueError:
                pass
    return 0.0


def _parse_work_date_from_form_data(data: dict) -> date | None:
    if not data:
        return None
    for k in ("work_date", "date"):
        if k in data and data[k]:
            try:
                return date.fromisoformat(str(data[k])[:10])
            except ValueError:
                continue
    return None


def _form_response_to_feed_item(fr: FormResponse, form_title: str, reg_name: str | None) -> ReportFeedItemOut:
    d = fr.data or {}
    wd = _parse_work_date_from_form_data(d)
    hours = _parse_hours_from_form_data(d)
    wt = (d.get("work_type") or "").strip()
    if "Техника" in wt or (d.get("activity_tech") and not d.get("activity_hand")):
        activity_grp = "техника"
        activity = d.get("activity_tech")
    else:
        activity_grp = "ручная"
        activity = d.get("activity_hand")
    location = d.get("location")
    return ReportFeedItemOut(
        source="form",
        id=fr.id,
        created_at=fr.submitted_at,
        user_id=fr.user_id,
        reg_name=reg_name,
        work_date=wd,
        hours=hours or None,
        location=location,
        location_grp=None,
        activity=activity,
        activity_grp=activity_grp,
        machine_type=d.get("machine_type"),
        machine_name=None,
        crop=d.get("crop"),
        trips=None,
        form_title=form_title,
    )


async def _merge_otd_feed_for_user(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int = 200,
) -> list[ReportFeedItemOut]:
    r_result = await db.execute(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(Report.work_date.desc(), Report.id.desc())
        .limit(limit)
    )
    reports = r_result.scalars().all()
    items: list[ReportFeedItemOut] = [
        ReportFeedItemOut(
            source="otd",
            id=r.id,
            created_at=r.created_at,
            user_id=r.user_id,
            reg_name=r.reg_name,
            work_date=r.work_date,
            hours=r.hours,
            location=r.location,
            location_grp=r.location_grp,
            activity=r.activity,
            activity_grp=r.activity_grp,
            machine_type=r.machine_type,
            machine_name=r.machine_name,
            crop=r.crop,
            trips=r.trips,
            form_title=None,
        )
        for r in reports
    ]

    ft_result = await db.execute(select(FormTemplate).where(FormTemplate.name == "otd"))
    otd_forms = ft_result.scalars().all()
    if not otd_forms:
        items.sort(key=lambda x: (x.work_date or date.min, x.created_at), reverse=True)
        return items[:limit]

    otd_ids = [f.id for f in otd_forms]
    title_by_id = {f.id: f.title for f in otd_forms}

    fr_result = await db.execute(
        select(FormResponse, User.full_name)
        .join(User, User.id == FormResponse.user_id)
        .where(FormResponse.user_id == user_id, FormResponse.form_id.in_(otd_ids))
        .order_by(FormResponse.submitted_at.desc())
        .limit(limit)
    )
    for fr, full_name in fr_result.all():
        items.append(
            _form_response_to_feed_item(fr, title_by_id.get(fr.form_id, "ОТД"), full_name)
        )

    items.sort(key=lambda x: (x.work_date or date.min, x.created_at), reverse=True)
    return items[:limit]


# ──────────────────────────── OTD Reports ────────────────────────────


@router.post("/reports", response_model=ReportOut, status_code=201)
async def create_report(
    body: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(
        select(func.sum(Report.hours)).where(
            and_(Report.user_id == current_user.id, Report.work_date == body.work_date)
        )
    )
    total_today = total_q.scalar() or 0
    if total_today + body.hours > 24:
        raise HTTPException(status_code=400, detail=f"Exceeds 24h limit for {body.work_date} (current: {total_today}h)")

    report = Report(
        user_id=current_user.id,
        reg_name=current_user.full_name,
        username=current_user.username,
        **body.model_dump(),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    await announce_classic_otd(report.id, current_user.id)
    return report


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    user_and_role: tuple = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    user, role = user_and_role
    q = select(Report)
    if role not in ("admin", "accountant"):
        q = q.where(Report.user_id == user.id)
    if date_from:
        q = q.where(Report.work_date >= date_from)
    if date_to:
        q = q.where(Report.work_date <= date_to)
    q = q.order_by(Report.work_date.desc(), Report.id.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/reports/feed", response_model=list[ReportFeedItemOut])
async def reports_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=200),
):
    """Список ОТД: классические записи + flow-форма «otd» (form_responses)."""
    return await _merge_otd_feed_for_user(db, current_user.id, limit=limit)


@router.get("/admin/otd-feed", response_model=list[ReportFeedItemOut])
async def admin_otd_feed(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(500, le=2000),
    _admin=Depends(require_accountant_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Все ОТД-отчёты за период: классика + flow «otd» (для админки)."""
    ft_result = await db.execute(select(FormTemplate).where(FormTemplate.name == "otd"))
    otd_forms = ft_result.scalars().all()
    otd_ids = [f.id for f in otd_forms] if otd_forms else []
    title_by_id = {f.id: f.title for f in otd_forms} if otd_forms else {}

    items: list[ReportFeedItemOut] = []

    rq = select(Report)
    if date_from:
        rq = rq.where(Report.work_date >= date_from)
    if date_to:
        rq = rq.where(Report.work_date <= date_to)
    rq = rq.order_by(Report.work_date.desc(), Report.id.desc()).limit(limit)
    r_result = await db.execute(rq)
    for r in r_result.scalars().all():
        items.append(
            ReportFeedItemOut(
                source="otd",
                id=r.id,
                created_at=r.created_at,
                user_id=r.user_id,
                reg_name=r.reg_name,
                work_date=r.work_date,
                hours=r.hours,
                location=r.location,
                location_grp=r.location_grp,
                activity=r.activity,
                activity_grp=r.activity_grp,
                machine_type=r.machine_type,
                machine_name=r.machine_name,
                crop=r.crop,
                trips=r.trips,
                form_title=None,
            )
        )

    if otd_ids:
        fq = (
            select(FormResponse, User.full_name)
            .join(User, User.id == FormResponse.user_id)
            .where(FormResponse.form_id.in_(otd_ids))
        )
        if date_from:
            fq = fq.where(cast(FormResponse.submitted_at, DateColumn) >= date_from)
        if date_to:
            fq = fq.where(cast(FormResponse.submitted_at, DateColumn) <= date_to)
        fq = fq.order_by(FormResponse.submitted_at.desc()).limit(limit)
        fr_result = await db.execute(fq)
        for fr, full_name in fr_result.all():
            items.append(
                _form_response_to_feed_item(fr, title_by_id.get(fr.form_id, "ОТД"), full_name)
            )

    items.sort(key=lambda x: (x.work_date or date.min, x.created_at), reverse=True)
    return items[:limit]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    return report


@router.patch("/reports/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: int,
    body: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    old_snapshot = {
        "work_date": str(report.work_date) if report.work_date else "",
        "location": report.location or "",
        "activity": report.activity or "",
        "activity_grp": report.activity_grp or "",
        "machine_type": report.machine_type or "",
        "crop": report.crop or "",
        "hours": str(report.hours) if report.hours is not None else "",
    }
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    await announce_classic_otd_edit(report.id, current_user.id, old_snapshot=old_snapshot)
    return report


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Not found")
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    snapshot = {
        "reg_name": report.reg_name, "work_date": str(report.work_date) if report.work_date else None,
        "location": report.location, "activity": report.activity, "activity_grp": report.activity_grp,
        "hours": report.hours,
    }
    await db.delete(report)
    await db.commit()
    await announce_classic_otd_delete(report_id, current_user.id, snapshot)


# ──────────────────────────── Brigadier Reports ────────────────────────────


@router.post("/brig/reports", response_model=BrigReportOut, status_code=201)
async def create_brig_report(
    body: BrigReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = BrigadierReport(
        user_id=current_user.id,
        username=current_user.username,
        **body.model_dump(),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    await announce_brig(report.id, current_user.id)
    return report


@router.patch("/brig/reports/{report_id}", response_model=BrigReportOut)
async def update_brig_report(
    report_id: int,
    body: BrigReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BrigadierReport).where(BrigadierReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    await announce_brig_edit(report.id, current_user.id)
    return report


@router.get("/brig/reports", response_model=list[BrigReportOut])
async def list_brig_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, le=200),
):
    q = select(BrigadierReport).where(BrigadierReport.user_id == current_user.id)
    if date_from:
        q = q.where(BrigadierReport.work_date >= date_from)
    if date_to:
        q = q.where(BrigadierReport.work_date <= date_to)
    q = q.order_by(BrigadierReport.work_date.desc()).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


# ──────────────────────────── Dynamic Form Responses ────────────────────────────


@router.post("/form-responses", response_model=FormResponseOut, status_code=201)
async def submit_form(
    body: FormResponseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resp = FormResponse(form_id=body.form_id, user_id=current_user.id, data=body.data)
    db.add(resp)
    await db.commit()
    await db.refresh(resp)
    await announce_form_otd(resp.id, current_user.id)
    return resp


@router.get("/form-responses", response_model=list[FormResponseOut])
async def list_form_responses(
    form_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(FormResponse).where(FormResponse.user_id == current_user.id)
    if form_id:
        q = q.where(FormResponse.form_id == form_id)
    result = await db.execute(q.order_by(FormResponse.submitted_at.desc()).limit(100))
    return result.scalars().all()


@router.get("/form-responses/{response_id}", response_model=FormResponseOut)
async def get_form_response(
    response_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FormResponse).where(FormResponse.id == response_id))
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Not found")
    if fr.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    return fr


@router.patch("/form-responses/{response_id}", response_model=FormResponseOut)
async def update_form_response(
    response_id: int,
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FormResponse).where(FormResponse.id == response_id))
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Not found")
    if fr.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    old_data = dict(fr.data or {})
    fr.data = {**fr.data, **body}
    flag_modified(fr, "data")
    await db.commit()
    await db.refresh(fr)
    await announce_form_otd_edit(fr.id, current_user.id, old_data=old_data)
    return fr


@router.delete("/form-responses/{response_id}", status_code=204)
async def delete_form_response(
    response_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FormResponse).where(FormResponse.id == response_id))
    fr = result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Not found")
    if fr.user_id != current_user.id:
        r = await db.execute(select(UserRole).where(UserRole.user_id == current_user.id))
        role_row = r.scalar_one_or_none()
        if not role_row or role_row.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    snapshot = dict(fr.data or {})
    stored_form_id = fr.form_id
    user = await db.get(User, fr.user_id)
    user_name = user.full_name if user else f"#{fr.user_id}"
    await db.delete(fr)
    await db.commit()
    await announce_form_otd_delete(response_id, current_user.id, snapshot, user_name, form_id=stored_form_id)


# ──────────────────────────── Statistics ────────────────────────────


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    period: str = Query("week", pattern="^(today|week|month)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    if period == "today":
        date_from = today
    elif period == "week":
        date_from = today - timedelta(days=7)
    else:
        date_from = today.replace(day=1)

    result = await db.execute(
        select(func.sum(Report.hours), func.count(Report.id)).where(
            and_(Report.user_id == current_user.id, Report.work_date >= date_from, Report.work_date <= today)
        )
    )
    row = result.one()
    total_hours = float(row[0] or 0)
    otd_count = int(row[1] or 0)

    fr_q = select(FormResponse).where(
        and_(
            FormResponse.user_id == current_user.id,
            cast(FormResponse.submitted_at, DateColumn) >= date_from,
            cast(FormResponse.submitted_at, DateColumn) <= today,
        )
    )
    frs = (await db.execute(fr_q)).scalars().all()
    form_dates: set[date] = set()
    for fr in frs:
        d = fr.data or {}
        total_hours += _parse_hours_from_form_data(d)
        wd = _parse_work_date_from_form_data(d)
        if wd:
            form_dates.add(wd)

    brig_q = await db.execute(
        select(func.count(BrigadierReport.id)).where(
            and_(
                BrigadierReport.user_id == current_user.id,
                BrigadierReport.work_date >= date_from,
                BrigadierReport.work_date <= today,
            )
        )
    )
    form_count = len(frs)
    report_count = otd_count + int(brig_q.scalar() or 0) + form_count

    rd_q = await db.execute(
        select(Report.work_date).where(
            and_(Report.user_id == current_user.id, Report.work_date >= date_from, Report.work_date <= today)
        ).distinct()
    )
    report_dates = {r[0] for r in rd_q.all() if r[0]}
    days_worked = len(report_dates | form_dates)

    return StatsOut(
        period=period,
        total_hours=total_hours,
        report_count=report_count,
        days_worked=days_worked,
    )
