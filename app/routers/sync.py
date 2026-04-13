"""Authenticated ingest endpoints for external services."""

from __future__ import annotations

import os
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.service.instagram_ingest import upsert_instagram_posts_batch

router = APIRouter(prefix="/sync", tags=["sync"])


def _expected_sync_api_key() -> str:
    return (os.environ.get("FOMO_SYNC_API_KEY") or "").strip()


def verify_fomo_sync_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = _expected_sync_api_key()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Ingest not configured (FOMO_SYNC_API_KEY is not set)",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer ") :].strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


class InstagramIngestBatch(BaseModel):
    batch_index: int
    batch_count: int
    rows: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/instagram-posts", dependencies=[Depends(verify_fomo_sync_key)])
def ingest_instagram_posts(
    body: InstagramIngestBatch,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not body.rows:
        return {"ok": True}

    try:
        upsert_instagram_posts_batch(db, body.rows)
        db.commit()
    except ValueError as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    except SQLAlchemyError as e:
        db.rollback()
        return {"ok": False, "error": f"database error: {e}"}

    return {"ok": True}
