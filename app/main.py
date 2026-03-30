from dataclasses import asdict

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.scraper import clean_raw_event, fetch_page_and_events, scrape_and_store

app = FastAPI(title="FOMO UCSD free-food scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "POST /scrape to fetch events and update temp_download/"}


@app.get("/events")
def list_events():
    """Live events from the same API as ucsd-free-food; shape matches cleaned JSON files."""
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        _, _, raw_events = fetch_page_and_events(client)
    out: list[dict] = []
    for row in raw_events:
        mid, cleaned = clean_raw_event(row)
        payload = asdict(cleaned)
        payload["id"] = mid
        out.append(payload)
    return out


@app.post("/scrape")
def scrape():
    """
    Scrapes https://sheeptester.github.io/ucsd-free-food/ (page HTML in memory)
    and loads events from the public API used by that site. Cleans fields:
    event_name, date, location, image, url. New events -> temp_download/*.json;
    duplicates are printed to server logs and listed in the response.
    """
    result = scrape_and_store()
    result.pop("raw_html", None)
    visible = (result.get("page_parsed") or {}).get("visible_text") or ""
    result["raw_html_preview"] = visible[:500]
    result["raw_html_stored_in_memory"] = True
    return result
