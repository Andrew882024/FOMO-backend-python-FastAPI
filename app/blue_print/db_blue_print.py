"""SQLAlchemy table definitions and session helpers for route blueprints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

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


class InstagramPosts(Base):
    """One row per scraped Instagram post (and optional AI enrichment)."""

    __tablename__ = "instagram_posts"
    __table_args__ = (
        UniqueConstraint(
            "profile_username",
            "post_shortcode",
            name="uq_instagram_posts_profile_username_post_shortcode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    post_shortcode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    post_url: Mapped[str] = mapped_column(Text, nullable=False)
    post_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_unix_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    posted_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    instagram_media_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_image_urls: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    is_event: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    event_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_in_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_analyzed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    event_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    own_s3_url_for_main_image: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "Event",
    "InstagramPosts",
    "LastScrape",
]


