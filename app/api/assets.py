"""POST/GET/HEAD assets — основной endpoint media-сервиса.

POST — multipart upload, sha256-dedup, save в shard-путь, insert row.
GET — stream бинарника с immutable-кэшем.
HEAD — те же headers без тела (для exists-check).
"""
import time
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import current_uploader
from app.core.exceptions import APIError
from app.core.storage import promote_tmp, save_stream, shard_path, thumb_path
from app.core.thumbs import THUMB_MIME, gen_thumb, is_image_mime, validate_image
from app.core.transcode import sha256_of_file, transcode_progressive_jpeg
from app.models.models import Asset
from app.schemas.asset import AssetResponse

router = APIRouter(prefix="/assets", tags=["assets"])

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
CHUNK = 64 * 1024


def _mime_allowed(mime: str) -> bool:
    if not mime:
        return False
    for prefix in settings.allowed_mime_list:
        if mime.startswith(prefix):
            return True
    return False


async def _chunks_from_upload(upload: UploadFile):
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        yield chunk


@router.post("", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    uploader: str = Depends(current_uploader),
):
    mime = (file.content_type or "").lower()
    if not _mime_allowed(mime):
        raise APIError(415, "unsupported_media_type", f"mime not allowed: {mime}")

    sha256, total, tmp_path = await save_stream(
        _chunks_from_upload(file), settings.max_upload_bytes
    )

    if is_image_mime(mime):
        try:
            validate_image(tmp_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    # Прогрессивный JPEG → blur-first рендер на медленных сетях.
    # Карта `2026-06-07-progressive-image-preview.md`. Не-JPEG / уже-progressive
    # → no-op (False), sha256 не меняем.
    if mime == "image/jpeg" and transcode_progressive_jpeg(tmp_path):
        sha256, total = sha256_of_file(tmp_path)

    existing = (await db.execute(select(Asset).where(Asset.sha256 == sha256))).scalar_one_or_none()
    if existing:
        tmp_path.unlink(missing_ok=True)
        return _to_response(existing, deduplicated=True)

    blob_path = promote_tmp(tmp_path, sha256)

    has_thumb = False
    thumb_bytes_size: int | None = None
    if is_image_mime(mime):
        thumb_bytes_size = gen_thumb(blob_path, thumb_path(sha256))
        has_thumb = True

    asset = Asset(
        id=uuid.uuid4(),
        sha256=sha256,
        mime=mime,
        bytes=total,
        has_thumb=has_thumb,
        thumb_mime=THUMB_MIME if has_thumb else None,
        thumb_bytes=thumb_bytes_size,
        uploaded_by=uploader,
        created_at=int(time.time() * 1000),
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _to_response(asset, deduplicated=False)


def _to_response(asset: Asset, *, deduplicated: bool) -> AssetResponse:
    return AssetResponse(
        id=asset.id,
        url=f"/api/v1/assets/{asset.id}",
        thumb_url=f"/api/v1/assets/{asset.id}/thumb" if asset.has_thumb else None,
        mime=asset.mime,
        bytes=asset.bytes,
        sha256=asset.sha256,
        deduplicated=deduplicated,
    )


async def _load_active(db: AsyncSession, asset_id: uuid.UUID) -> Asset:
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id))
    ).scalar_one_or_none()
    if asset is None or asset.deleted_at is not None:
        raise APIError(404, "not_found", "asset not found")
    return asset


def _file_for(asset: Asset) -> Path:
    path = shard_path(asset.sha256)
    if not path.exists():
        raise APIError(404, "not_found", "asset blob missing on disk")
    return path


@router.get("/{asset_id}")
async def get_asset(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    asset = await _load_active(db, asset_id)
    path = _file_for(asset)

    async def stream():
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(CHUNK)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=asset.mime,
        headers={
            "Cache-Control": IMMUTABLE_CACHE,
            "Content-Length": str(asset.bytes),
            "ETag": f'"{asset.sha256}"',
        },
    )


@router.head("/{asset_id}")
async def head_asset(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    asset = await _load_active(db, asset_id)
    _file_for(asset)
    return Response(
        status_code=200,
        media_type=asset.mime,
        headers={
            "Cache-Control": IMMUTABLE_CACHE,
            "Content-Length": str(asset.bytes),
            "ETag": f'"{asset.sha256}"',
        },
    )


@router.get("/{asset_id}/thumb")
async def get_asset_thumb(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    asset = await _load_active(db, asset_id)
    if not asset.has_thumb:
        raise APIError(404, "no_thumb", "asset has no thumbnail")
    path = thumb_path(asset.sha256)
    if not path.exists():
        raise APIError(404, "no_thumb", "thumbnail missing on disk")

    async def stream():
        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(CHUNK)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=asset.thumb_mime or "image/webp",
        headers={
            "Cache-Control": IMMUTABLE_CACHE,
            "Content-Length": str(asset.thumb_bytes or path.stat().st_size),
            "ETag": f'"{asset.sha256}.thumb"',
        },
    )
