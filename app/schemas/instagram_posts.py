"""Response models for Instagram post listings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnrichedInstagramPost(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_url: str
    post_shortcode: str
    is_event: bool
    event_title: str
    provider_name: str
    post_description: str
    location: str
    duration_in_minutes: int
    confidence: str | None
    ai_model: str | None
    ai_analyzed: bool
    event_start_at: datetime
    own_s3_url_for_main_image: str
