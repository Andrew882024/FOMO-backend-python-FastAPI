"""
Background scrape schedule:
- On startup: scrape if the DB has no events, no LastScrape row, or last scrape was ≥24h ago.
- After each successful scrape, sleep until last_scrape.timestamp + 24 hours (rolling window).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blue_print.db_blue_print import Event, LastScrape
from app.database import SessionLocal
from app.scraper import scrape_and_store

INTERVAL = timedelta(hours=24)
# If scrape fails or LastScrape is missing, retry after this many seconds.
RETRY_SECONDS = 60.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _should_scrape_now(db: Session) -> bool:
    n = db.scalar(select(func.count()).select_from(Event))
    if n == 0:
        return True
    ls = db.get(LastScrape, 1)
    if ls is None:
        return True
    return _utcnow() - ls.timestamp >= INTERVAL


def _seconds_until_next_window(db: Session) -> float | None:
    """Sleep duration until last_scrape.timestamp + INTERVAL. None if unknown (retry soon)."""
    ls = db.get(LastScrape, 1)
    if ls is None:
        return None
    next_run = ls.timestamp + INTERVAL
    return max(0.0, (next_run - _utcnow()).total_seconds())


async def periodic_scrape_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            run_now = _should_scrape_now(db)
        finally:
            db.close()

        if run_now:
            try:
                await asyncio.to_thread(scrape_and_store)
            except Exception as e:
                print(f"[fetch_every_24_hours] scrape failed: {e}", flush=True)
                await asyncio.sleep(RETRY_SECONDS)
                continue

        db = SessionLocal()
        try:
            wait = _seconds_until_next_window(db)
        finally:
            db.close()

        if wait is None:
            await asyncio.sleep(RETRY_SECONDS)
        elif wait <= 0:
            continue
        else:
            await asyncio.sleep(wait)
