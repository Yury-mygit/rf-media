from uuid import UUID

from app.schemas.common import CamelModel


class AssetResponse(CamelModel):
    id: UUID
    url: str
    thumb_url: str | None
    mime: str
    bytes: int
    sha256: str
    deduplicated: bool
