from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.scraper import load_events_from_temp_download, scrape_and_store

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
    outcomes = load_events_from_temp_download()
    if len(outcomes) == 0:
        scrape_and_store()
        outcomes = load_events_from_temp_download()
    """Events from temp_download/*.json (populated by POST /scrape); no live fetch."""
    return outcomes


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
