"""Файловое хранилище asset'ов: двухуровневый шардинг по sha256 + atomic save."""
import hashlib
import os
import tempfile
from pathlib import Path

import aiofiles

from app.core.config import settings


def shard_path(sha256: str, root: str | None = None) -> Path:
    """`<root>/<aa>/<bb>/<sha256>` — двухуровневый шардинг для размазывания
    миллионов файлов по поддиректориям (ext4 не любит >10k файлов в одной)."""
    base = Path(root or settings.storage_root)
    return base / sha256[:2] / sha256[2:4] / sha256


def thumb_path(sha256: str, root: str | None = None) -> Path:
    """`<root>/thumbs/<aa>/<bb>/<sha256>.webp`."""
    base = Path(root or settings.storage_root)
    return base / "thumbs" / sha256[:2] / sha256[2:4] / f"{sha256}.webp"


async def save_stream(chunks_iter, max_bytes: int) -> tuple[str, int, Path]:
    """Стримит chunks во временный файл, считает sha256 и размер.
    На превышении max_bytes — APIError(413). Возвращает (sha256, bytes, tmp_path).
    Tmp лежит в STORAGE_ROOT/tmp (тот же FS, чтобы потом os.rename был atomic)."""
    from app.core.exceptions import APIError

    tmp_dir = Path(settings.storage_root) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=tmp_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)

    h = hashlib.sha256()
    total = 0
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            async for chunk in chunks_iter:
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise APIError(413, "too_large", f"upload exceeds {max_bytes} bytes")
                h.update(chunk)
                await f.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return h.hexdigest(), total, tmp_path


def promote_tmp(tmp_path: Path, sha256: str) -> Path:
    """Перемещает tmp-файл в окончательный shard-путь. Idempotent:
    если файл там уже есть (dedup), tmp удаляется."""
    final = shard_path(sha256)
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        tmp_path.unlink(missing_ok=True)
    else:
        os.replace(tmp_path, final)
    return final
