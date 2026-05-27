"""Endpoints GC: /gc/run (ad-hoc, curator) + /gc/last (статус последнего прохода)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_curator
from app.core.exceptions import APIError
from app.models.models import GcRun
from app.services.gc import run_gc

router = APIRouter(prefix="/gc", tags=["gc"])


def _serialize(run: GcRun) -> dict:
    return {
        "id": str(run.id),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "status": run.status,
        "consumers_ok": run.consumers_ok,
        "consumers_failed": run.consumers_failed,
        "total_refs": run.total_refs,
        "deleted": run.deleted,
        "error_text": run.error_text,
    }


@router.post("/run")
async def gc_run(
    grace_seconds: int | None = Query(default=None, ge=0),
    _email: str = Depends(current_curator),
):
    """Ad-hoc запуск GC. `grace_seconds` (опц.) переопределяет grace_days из env —
    нужно для smoke (передать 0 → удалить все orphan без выдержки)."""
    run = await run_gc(grace_seconds_override=grace_seconds)
    return _serialize(run)


@router.get("/last")
async def gc_last(
    db: AsyncSession = Depends(get_db),
    _email: str = Depends(current_curator),
):
    row = (
        await db.execute(
            select(GcRun).order_by(GcRun.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise APIError(404, "no_runs", "no GC runs yet")
    return _serialize(row)
