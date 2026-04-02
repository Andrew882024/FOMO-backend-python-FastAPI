"""SQLAlchemy table definitions and session helpers for route blueprints."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SessionLocal, engine, get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    """Stored free-food event (source _id from UCSD API)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(512))
    date: Mapped[str] = mapped_column(String(512))
    location: Mapped[str] = mapped_column(String(512))
    image: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class LastScrape(Base):
    """Singleton row (id=1): last successful scrape time."""

    __tablename__ = "last_scrape"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


__all__ = ["Base", "SessionLocal", "engine", "get_db", "Event", "LastScrape"]


