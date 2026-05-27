import uuid

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    mime: Mapped[str] = mapped_column(String(80), nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    has_thumb: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    thumb_mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    thumb_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class GcRun(Base):
    __tablename__ = "gc_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    consumers_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumers_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_refs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_text: Mapped[str | None] = mapped_column(String, nullable=True)
