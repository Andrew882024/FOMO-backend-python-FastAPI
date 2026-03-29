from fastapi import FastAPI

from app.scraper import scrape_and_store

app = FastAPI(title="FOMO UCSD free-food scraper")


@app.get("/")
def root():
    return {"message": "POST /scrape to fetch events and update temp_download/"}


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
