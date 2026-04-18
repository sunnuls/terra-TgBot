"""ARQ background worker tasks."""
import logging
from datetime import date, timedelta
from arq import cron

logger = logging.getLogger(__name__)


async def daily_export(ctx):
    """Daily auto-export: generate OTD Excel for yesterday."""
    from app.core.database import AsyncSessionLocal
    from app.models.report import Report
    from app.services.excel_export import build_otd_excel
    from sqlalchemy import select, and_
    import os

    yesterday = date.today() - timedelta(days=1)
    export_dir = "/tmp/terra_exports"
    os.makedirs(export_dir, exist_ok=True)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Report).where(
                and_(Report.work_date >= yesterday, Report.work_date <= yesterday)
            ).order_by(Report.user_id)
        )
        reports = result.scalars().all()
        if reports:
            filepath = os.path.join(export_dir, f"daily_otd_{yesterday}.xlsx")
            await build_otd_excel(reports, filepath)
            logger.info("Daily export done: %s (%d reports)", filepath, len(reports))


async def startup(ctx):
    logger.info("ARQ worker started")


async def shutdown(ctx):
    logger.info("ARQ worker stopped")


class WorkerSettings:
    functions = [daily_export]
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        cron(daily_export, hour=2, minute=0)  # runs daily at 02:00
    ]
    redis_settings = None  # set from config at runtime
