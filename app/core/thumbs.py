"""Thumbnail-генерация: 256×256 WebP из image/* через Pillow.

Side-effect: открывает картинку через Pillow → validation сигнатуры.
Если incoming mime image/* но Pillow не парсит — APIError(415). Это закрывает
дыру с mime spoofing (загрузил .sh с заголовком image/png).
"""
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.exceptions import APIError

THUMB_MAX = (256, 256)
THUMB_QUALITY = 80
THUMB_MIME = "image/webp"


def is_image_mime(mime: str) -> bool:
    return mime.startswith("image/")


def validate_image(src_path: Path) -> None:
    """Открывает файл через Pillow для проверки сигнатуры. Если не картинка
    (incoming mime spoofed) → APIError(415). Не сохраняет результат —
    предназначен для проверки ДО promote_tmp, чтобы не оставлять orphan-blob."""
    try:
        with Image.open(src_path) as im:
            im.verify()
    except (UnidentifiedImageError, Exception) as e:
        raise APIError(415, "unsupported_media_type", f"not a valid image: {e}") from e


def gen_thumb(src_path: Path, dst_path: Path) -> int:
    """Читает src, ресайзит до 256×256 (aspect-preserving), пишет в dst как WebP.
    Возвращает размер dst в байтах. На UnidentifiedImageError — APIError(415).
    GIF — берётся первый кадр."""
    try:
        with Image.open(src_path) as im:
            im.load()
            if im.mode in ("RGBA", "LA"):
                background = Image.new("RGBA", im.size, (255, 255, 255, 0))
                background.paste(im, mask=im.split()[-1])
                im = background
            elif im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail(THUMB_MAX)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst_path, format="WEBP", quality=THUMB_QUALITY, method=4)
    except UnidentifiedImageError as e:
        raise APIError(415, "unsupported_media_type", f"not a valid image: {e}") from e

    return dst_path.stat().st_size
