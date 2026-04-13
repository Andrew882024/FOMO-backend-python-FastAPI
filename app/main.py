import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, ensure_schema, get_db
from app.routers.instagram_posts import router as instagram_posts_router
from app.routers.sync import router as sync_router
from app.scraper import load_events_from_db, scrape_and_store
from app.service.fetch_every_24_hours import periodic_scrape_loop
import app.blue_print.db_blue_print  # noqa: F401 — register tables before create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    task = asyncio.create_task(periodic_scrape_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="FOMO UCSD free-food scraper", lifespan=lifespan)

app.include_router(sync_router)
app.include_router(instagram_posts_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
       "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "POST /scrape to fetch events and store them in Postgres"}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"database": "ok"}


@app.get("/events")
def list_events(db: Session = Depends(get_db)):
    return load_events_from_db(db)


@app.post("/scrape")
def scrape():
    """
    Scrapes https://sheeptester.github.io/ucsd-free-food/ (page HTML in memory)
    and loads events from the public API used by that site. Cleans fields:
    event_name, date, location, image, url. New events are inserted into Postgres;
    duplicates are printed to server logs and listed in the response.
    """
    result = scrape_and_store()
    result.pop("raw_html", None)
    visible = (result.get("page_parsed") or {}).get("visible_text") or ""
    result["raw_html_preview"] = visible[:500]
    result["raw_html_stored_in_memory"] = True
    return result
