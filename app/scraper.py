"""UCSD free-food list: page fetch + API parse (same data as the public site)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

FREE_FOOD_PAGE_URL = "https://sheeptester.github.io/ucsd-free-food/"
FREE_FOOD_API_BASE = "https://sheep.thingkingland.app/free-food"

LA = ZoneInfo("America/Los_Angeles")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def temp_download_dir() -> Path:
    d = _project_root() / "temp_download"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fmt_ampm(dt: datetime) -> str:
    s = dt.strftime("%I:%M %p")
    return s[1:] if s.startswith("0") else s


def _format_event_date(
    date_part: dict,
    start: dict | None,
    end: dict | None,
) -> str:
    y, mo, day = int(date_part["year"]), int(date_part["month"]), int(date_part["date"])
    start = start or {"hour": 0, "minute": 0}
    sh, sm = int(start["hour"]), int(start["minute"])
    try:
        start_dt = datetime(y, mo, day, sh, sm, tzinfo=LA)
    except ValueError:
        return f"{y}-{mo:02d}-{day:02d} (date as provided by source)"

    head = f"{_MONTHS[mo - 1]} {day}, {y}, {_fmt_ampm(start_dt)}"
    if end is not None:
        eh, em = int(end["hour"]), int(end["minute"])
        try:
            end_dt = datetime(y, mo, day, eh, em, tzinfo=LA)
        except ValueError:
            return head
        if end_dt != start_dt:
            return f"{head} – {_fmt_ampm(end_dt)}"
    return head


@dataclass
class CleanedEvent:
    event_name: str
    date: str
    location: str
    image: str | None
    url: str


def clean_raw_event(raw: dict) -> tuple[str, CleanedEvent]:
    """Returns (mongo_id, cleaned)."""
    mongo_id = str(raw["_id"])
    foods = raw.get("freeFood") or []
    if foods:
        event_name = "Free " + ", ".join(str(f) for f in foods)
    else:
        event_name = "Free event"
    date_str = _format_event_date(
        raw["date"],
        raw.get("start"),
        raw.get("end"),
    )
    loc = (raw.get("location") or "").strip() or "Not specified"
    has_image = bool(raw.get("i"))
    image = f"{FREE_FOOD_API_BASE}/{mongo_id}/img.webp" if has_image else None
    url = (raw.get("url") or "").strip()
    return mongo_id, CleanedEvent(
        event_name=event_name,
        date=date_str,
        location=loc,
        image=image,
        url=url,
    )


def parse_page_html(raw_html: str) -> BeautifulSoup:
    """BeautifulSoup tree for the scraped page (static HTML only for this URL)."""
    return BeautifulSoup(raw_html, "html.parser")


def extract_page_fields(soup: BeautifulSoup) -> dict[str, str]:
    """Pull structured fields from the document using BeautifulSoup."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""
    desc_el = soup.find("meta", attrs={"name": "description"})
    description = (desc_el.get("content") or "").strip() if desc_el else ""
    og = soup.find("meta", attrs={"property": "og:image"})
    og_image = (og.get("content") or "").strip() if og else ""
    visible = " ".join(soup.get_text(separator=" ", strip=True).split())
    return {
        "title": title,
        "description": description,
        "og_image": og_image,
        "visible_text": visible,
    }


def fetch_page_and_events(
    client: httpx.Client,
    *,
    on_or_after: str | None = None,
) -> tuple[str, BeautifulSoup, list[dict]]:
    """
    1) Raw HTML from the public page (SPA shell; list is loaded via API in the browser).
    2) Parsed BeautifulSoup of that HTML.
    3) Event records from the same JSON API the site uses.
    on_or_after: YYYY-MM-DD in calendar terms; defaults to today's date in America/Los_Angeles.
    """
    r = client.get(FREE_FOOD_PAGE_URL)
    r.raise_for_status()
    raw_html = r.text
    soup = parse_page_html(raw_html)

    if on_or_after is None:
        on_or_after = datetime.now(LA).date().isoformat()

    r2 = client.get(FREE_FOOD_API_BASE, params={"onOrAfter": on_or_after})
    r2.raise_for_status()
    raw_events: list[dict] = r2.json()
    return raw_html, soup, raw_events


def scrape_and_store() -> dict:
    """
    Fetches the page and API, builds cleaned events, saves new ones under temp_download/.
    Duplicates (already stored _id) are printed and omitted from new saves.
    """
    raw_html: str
    page_soup: BeautifulSoup
    raw_events: list[dict]
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        raw_html, page_soup, raw_events = fetch_page_and_events(client)

    page_parsed = extract_page_fields(page_soup)

    cleaned: list[CleanedEvent] = []
    ids_order: list[str] = []
    for row in raw_events:
        mid, c = clean_raw_event(row)
        ids_order.append(mid)
        cleaned.append(c)

    out_dir = temp_download_dir()
    new_saved: list[dict] = []
    duplicates: list[dict] = []

    for mid, event in zip(ids_order, cleaned):
        path = out_dir / f"{mid}.json"
        payload = asdict(event)
        if path.exists():
            duplicates.append({"_id": mid, **payload})
            print(f"[duplicate] {json.dumps({'_id': mid, **payload}, ensure_ascii=False)}")
            continue
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        new_saved.append({"_id": mid, **payload})

    # Variables requested: raw page, raw list, cleaned list (names only in response for size)
    return {
        "page_url": FREE_FOOD_PAGE_URL,
        "raw_html_length": len(raw_html),
        "raw_html": raw_html,
        "page_parsed": page_parsed,
        "raw_event_count": len(raw_events),
        "cleaned_events": [asdict(e) for e in cleaned],
        "new_stored": new_saved,
        "duplicates": duplicates,
        "temp_download": str(out_dir.resolve()),
    }


def strip_html_to_text(html: str) -> str:
    """Plain visible text from HTML using BeautifulSoup (scripts/styles removed)."""
    return extract_page_fields(parse_page_html(html))["visible_text"]
