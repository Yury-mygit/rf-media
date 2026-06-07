"""Перекодирование JPEG в progressive формат для blur-first рендера на
медленных сетях. Карта `cards/booking/feature/2026-06-07-progressive-image-preview.md`.

`quality="keep"` сохраняет оригинальные quantization tables — формально
lossless по отношению к декодированному изображению, меняется только
порядок DCT-scan'ов в файле. `optimize=True` пересоберёт Huffman-таблицы
(файл часто становится на 1-5% меньше).
"""
import hashlib
import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def is_progressive_jpeg(path: Path) -> bool:
    """True если файл — progressive JPEG; False если baseline или не JPEG."""
    try:
        with Image.open(path) as im:
            if im.format != "JPEG":
                return False
            return bool(im.info.get("progressive", False))
    except (UnidentifiedImageError, OSError):
        return False


def transcode_progressive_jpeg(path: Path) -> bool:
    """Если файл — baseline JPEG, перекодирует in-place в progressive
    атомарно (temp + rename). Возвращает True если файл был изменён.

    Не-JPEG или уже-progressive → no-op, return False."""
    try:
        with Image.open(path) as im:
            if im.format != "JPEG":
                return False
            if im.info.get("progressive"):
                return False
            im.load()
            tmp_path = path.with_suffix(path.suffix + ".prog.tmp")
            im.save(
                tmp_path,
                format="JPEG",
                progressive=True,
                quality="keep",
                optimize=True,
            )
        os.replace(tmp_path, path)
        return True
    except (UnidentifiedImageError, OSError):
        # Не критично — оригинал остаётся, upload пройдёт как раньше.
        return False


def sha256_of_file(path: Path) -> tuple[str, int]:
    """Возвращает (sha256, total_bytes) — для пересчёта после re-encode."""
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total
