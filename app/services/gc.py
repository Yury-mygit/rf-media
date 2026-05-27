"""Orphan GC: pull-модель. Опрашиваем consumers за shared secret, собираем
union refs, soft-delete + unlink assets, на которые никто не ссылается дольше
grace-периода. Abort всего прохода если хоть один consumer недоступен — без
полной картины refs удалять опасно.
"""
import logging
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.storage import shard_path, thumb_path
from app.models.models import Asset, GcRun

log = logging.getLogger("media.gc")

CONSUMER_TIMEOUT_S = 10
DEFAULT_GRACE_MS_PER_DAY = 86_400_000


async def fetch_consumer_refs(client: httpx.AsyncClient, name: str, url: str) -> set[str]:
    """GET <url> с X-Media-GC-Token. Возвращает set[asset_id]. На любой ошибке
    или non-200 — пробрасывает исключение (вызывающий abort'ит проход)."""
    resp = await client.get(
        url,
        headers={"X-Media-GC-Token": settings.media_gc_token},
        timeout=CONSUMER_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    ids = data.get("asset_ids") or []
    return {str(x) for x in ids}


async def _unlink_blobs(sha256: str, has_thumb: bool) -> None:
    """Best-effort удаление blob + thumb. Ошибки логируем, не падаем (если
    файла уже нет — это и есть желаемое состояние)."""
    paths: list[Path] = [shard_path(sha256)]
    if has_thumb:
        paths.append(thumb_path(sha256))
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except Exception as e:
            log.warning("unlink failed: %s: %r", p, e)


async def run_gc(*, grace_seconds_override: int | None = None) -> GcRun:
    """Один проход GC. Создаёт запись gc_runs, возвращает её (уже с финальным
    status/счётчиками). НЕ raise'ит — фиксирует error в gc_runs.error_text."""
    started = int(time.time() * 1000)
    grace_ms = (
        grace_seconds_override * 1000
        if grace_seconds_override is not None
        else settings.media_gc_grace_days * DEFAULT_GRACE_MS_PER_DAY
    )
    run_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        gc_run = GcRun(
            id=run_id,
            started_at=started,
            status="running",
            consumers_ok=0,
            consumers_failed=0,
            total_refs=0,
            deleted=0,
        )
        db.add(gc_run)
        await db.commit()

    consumers = settings.consumer_list
    if not consumers:
        return await _finalize(run_id, status="aborted", error_text="no consumers configured")

    referenced: set[str] = set()
    ok = failed = 0
    async with httpx.AsyncClient() as client:
        for name, url in consumers:
            try:
                refs = await fetch_consumer_refs(client, name, url)
                referenced |= refs
                ok += 1
                log.info("gc: consumer %s ok, %d refs", name, len(refs))
            except Exception as e:
                failed += 1
                log.error("gc: consumer %s failed: %r", name, e)
                return await _finalize(
                    run_id,
                    status="aborted",
                    consumers_ok=ok,
                    consumers_failed=failed,
                    total_refs=len(referenced),
                    error_text=f"consumer {name} unreachable: {e!r}",
                )

    deleted = 0
    async with AsyncSessionLocal() as db:
        cutoff = started - grace_ms
        stmt = select(Asset).where(
            Asset.deleted_at.is_(None), Asset.created_at < cutoff
        )
        rows = (await db.execute(stmt)).scalars().all()
        for asset in rows:
            if str(asset.id) in referenced:
                continue
            await _unlink_blobs(asset.sha256, asset.has_thumb)
            asset.deleted_at = started
            deleted += 1
        await db.commit()

    return await _finalize(
        run_id,
        status="ok",
        consumers_ok=ok,
        consumers_failed=failed,
        total_refs=len(referenced),
        deleted=deleted,
    )


async def _finalize(
    run_id: uuid.UUID,
    *,
    status: str,
    consumers_ok: int = 0,
    consumers_failed: int = 0,
    total_refs: int = 0,
    deleted: int = 0,
    error_text: str | None = None,
) -> GcRun:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(GcRun)
            .where(GcRun.id == run_id)
            .values(
                finished_at=int(time.time() * 1000),
                status=status,
                consumers_ok=consumers_ok,
                consumers_failed=consumers_failed,
                total_refs=total_refs,
                deleted=deleted,
                error_text=error_text,
            )
        )
        await db.commit()
        return (await db.execute(select(GcRun).where(GcRun.id == run_id))).scalar_one()
