"""Parse Instagram sync payloads and upsert into instagram_posts (PostgreSQL)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.blue_print.db_blue_print import InstagramPosts


def _parse_optional_dt(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError as e:
            raise ValueError(f"{field}: invalid ISO datetime") from e
    raise ValueError(f"{field}: expected string or null, got {type(value).__name__}")


def _parse_optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field}: unexpected bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raise ValueError(f"{field}: expected int or null, got {type(value).__name__}")


def _parse_optional_bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field}: expected bool or null, got {type(value).__name__}")


def _optional_str(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    raise ValueError(f"{field}: expected string or null, got {type(value).__name__}")


def _jsonb_value(value: Any, field: str) -> Any | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    raise ValueError(f"{field}: expected object, array, or null, got {type(value).__name__}")


def _require_str(value: Any, field: str) -> str:
    if value is None or not isinstance(value, str):
        raise ValueError(f"{field}: required non-empty string")
    s = value.strip()
    if not s:
        raise ValueError(f"{field}: required non-empty string")
    return s


def row_dict_to_upsert_values(row: dict[str, Any]) -> dict[str, Any]:
    """Build column map for insert/upsert; ignores source `id`."""
    parsed_ca = _parse_optional_dt(row.get("created_at"), "created_at")
    parsed_ua = _parse_optional_dt(row.get("updated_at"), "updated_at")
    raw_ai = row.get("ai_analyzed")
    if raw_ai is None:
        ai_analyzed = False
    elif isinstance(raw_ai, bool):
        ai_analyzed = raw_ai
    else:
        raise ValueError("ai_analyzed: expected bool or null")

    return {
        "profile_username": _require_str(row.get("profile_username"), "profile_username"),
        "post_shortcode": _require_str(row.get("post_shortcode"), "post_shortcode"),
        "post_url": _require_str(row.get("post_url"), "post_url"),
        "post_title": _optional_str(row.get("post_title"), "post_title"),
        "posted_unix_seconds": _parse_optional_int(row.get("posted_unix_seconds"), "posted_unix_seconds"),
        "posted_time": _parse_optional_dt(row.get("posted_time"), "posted_time"),
        "instagram_media_id": _optional_str(row.get("instagram_media_id"), "instagram_media_id"),
        "caption": _optional_str(row.get("caption"), "caption"),
        "comments_json": _jsonb_value(row.get("comments_json"), "comments_json"),
        "main_image_url": _optional_str(row.get("main_image_url"), "main_image_url"),
        "additional_image_urls": _jsonb_value(
            row.get("additional_image_urls"), "additional_image_urls"
        ),
        "is_event": _parse_optional_bool(row.get("is_event"), "is_event"),
        "event_title": _optional_str(row.get("event_title"), "event_title"),
        "provider_name": _optional_str(row.get("provider_name"), "provider_name"),
        "post_description": _optional_str(row.get("post_description"), "post_description"),
        "location": _optional_str(row.get("location"), "location"),
        "duration_in_minutes": _parse_optional_int(row.get("duration_in_minutes"), "duration_in_minutes"),
        "confidence": _optional_str(row.get("confidence"), "confidence"),
        "ai_model": _optional_str(row.get("ai_model"), "ai_model"),
        "ai_analyzed": ai_analyzed,
        "event_start_at": _parse_optional_dt(row.get("event_start_at"), "event_start_at"),
        "event_end_at": _parse_optional_dt(row.get("event_end_at"), "event_end_at"),
        "own_s3_url_for_main_image": _optional_str(
            row.get("own_s3_url_for_main_image"), "own_s3_url_for_main_image"
        ),
        "created_at": parsed_ca if parsed_ca is not None else func.now(),
        "updated_at": parsed_ua,
    }


def upsert_instagram_posts_batch(session: Session, rows: list[dict[str, Any]]) -> None:
    """Insert or update rows by (profile_username, post_shortcode). Caller commits."""
    if not rows:
        return

    parsed: list[dict[str, Any]] = []
    for i, raw in enumerate(rows):
        try:
            parsed.append(row_dict_to_upsert_values(raw))
        except ValueError as e:
            raise ValueError(f"batch row {i}: {e}") from e

    stmt = insert(InstagramPosts).values(parsed)
    ex = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_instagram_posts_profile_username_post_shortcode",
        set_={
            "post_url": ex.post_url,
            "post_title": ex.post_title,
            "posted_unix_seconds": ex.posted_unix_seconds,
            "posted_time": ex.posted_time,
            "instagram_media_id": ex.instagram_media_id,
            "caption": ex.caption,
            "comments_json": ex.comments_json,
            "main_image_url": ex.main_image_url,
            "additional_image_urls": ex.additional_image_urls,
            "is_event": ex.is_event,
            "event_title": ex.event_title,
            "provider_name": ex.provider_name,
            "post_description": ex.post_description,
            "location": ex.location,
            "duration_in_minutes": ex.duration_in_minutes,
            "confidence": ex.confidence,
            "ai_model": ex.ai_model,
            "ai_analyzed": ex.ai_analyzed,
            "event_start_at": ex.event_start_at,
            "event_end_at": ex.event_end_at,
            "own_s3_url_for_main_image": ex.own_s3_url_for_main_image,
            "created_at": InstagramPosts.created_at,
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)
