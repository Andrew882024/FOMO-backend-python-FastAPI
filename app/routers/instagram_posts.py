"""Public read API for enriched Instagram posts."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.blue_print.db_blue_print import InstagramPosts
from app.database import get_db
from app.schemas.instagram_posts import EnrichedInstagramPost

router = APIRouter(prefix="/instagram-posts", tags=["instagram-posts"])


def _trim_non_empty(column):
    return and_(column.isnot(None), func.length(func.trim(column)) > 0)


@router.get("", response_model=list[EnrichedInstagramPost])
def list_enriched_instagram_posts(db: Session = Depends(get_db)) -> list[EnrichedInstagramPost]:
    stmt = (
        select(InstagramPosts)
        .where(
            and_(
                InstagramPosts.is_event.is_(True),
                InstagramPosts.ai_analyzed.is_(True),
                               InstagramPosts.event_start_at.isnot(None),
                _trim_non_empty(InstagramPosts.event_title),
                _trim_non_empty(InstagramPosts.provider_name),
                _trim_non_empty(InstagramPosts.post_description),
                _trim_non_empty(InstagramPosts.location),
                _trim_non_empty(InstagramPosts.own_s3_url_for_main_image),
            )
        )
        .order_by(InstagramPosts.event_start_at.asc(), InstagramPosts.id.asc())
    )
    rows = db.scalars(stmt).all()
    return [
        EnrichedInstagramPost.model_validate(
            {
                "id": r.id,
                "post_url": r.post_url,
                "post_shortcode": r.post_shortcode,
                "is_event": r.is_event,
                "event_title": r.event_title,
                "provider_name": r.provider_name,
                "post_description": r.post_description,
                "location": r.location,
                "duration_in_minutes": 1
                if r.duration_in_minutes is None
                else r.duration_in_minutes,
                "confidence": r.confidence,
                "ai_model": r.ai_model,
                "ai_analyzed": r.ai_analyzed,
                "event_start_at": r.event_start_at,
                "own_s3_url_for_main_image": r.own_s3_url_for_main_image,
            }
        )
        for r in rows
    ]
