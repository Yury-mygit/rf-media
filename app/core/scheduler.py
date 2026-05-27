"""APScheduler init + lifecycle. Cron 03:00 UTC — раз в сутки orphan GC."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.services.gc import run_gc

log = logging.getLogger("media.scheduler")

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if not settings.media_gc_enabled:
        log.info("scheduler: gc disabled by env")
        return
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        run_gc,
        CronTrigger(hour=settings.media_gc_cron_hour, minute=0, timezone="UTC"),
        id="orphan_gc",
        replace_existing=True,
    )
    _scheduler.start()
    log.info("scheduler: started, gc cron %d:00 UTC", settings.media_gc_cron_hour)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
