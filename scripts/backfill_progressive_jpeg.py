"""Разовый bulk-перевод baseline JPEG → progressive для существующих ассетов.

Карта: `cards/booking/feature/2026-06-07-progressive-image-preview.md`, Stage 2.

Запуск внутри контейнера:

    docker exec media_dev_app python scripts/backfill_progressive_jpeg.py --dry-run
    docker exec media_dev_app python scripts/backfill_progressive_jpeg.py

sha256 в DB **не обновляется** — это известный drift, см. трейд-офф в карте.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.storage import shard_path
from app.core.transcode import is_progressive_jpeg, transcode_progressive_jpeg
from app.models.models import Asset


async def main(dry_run: bool) -> None:
    stats = {
        "scanned": 0,
        "already_progressive": 0,
        "converted": 0,
        "missing": 0,
        "errors": 0,
    }
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Asset).where(Asset.mime == "image/jpeg", Asset.deleted_at.is_(None))
            )
        ).scalars().all()
        for a in rows:
            stats["scanned"] += 1
            path = shard_path(a.sha256)
            if not path.exists():
                stats["missing"] += 1
                print(f"  MISSING blob: {a.id} ({a.sha256[:12]}…)", file=sys.stderr)
                continue
            if is_progressive_jpeg(path):
                stats["already_progressive"] += 1
                continue
            if dry_run:
                print(f"  DRY: {a.id} ({a.sha256[:12]}…) — baseline, would convert")
                stats["converted"] += 1
                continue
            try:
                changed = transcode_progressive_jpeg(path)
                if changed:
                    stats["converted"] += 1
                    print(f"  OK: {a.id} ({a.sha256[:12]}…) → progressive")
                else:
                    stats["already_progressive"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR: {a.id} ({a.sha256[:12]}…) — {e}", file=sys.stderr)

    print("\nStats:", stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
