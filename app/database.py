from __future__ import annotations

import os
import socket
from collections.abc import Generator
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_DEFAULT_LOCAL = "postgresql+psycopg2://fomo:fomo_local@localhost:5432/fomo_test"


def _first_ipv4(host: str) -> str | None:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return None
    return infos[0][4][0] if infos else None


def _is_supabase_pooler_host(host: str) -> bool:
    return "pooler.supabase.com" in host


def _validate_pooler_credentials(host: str, user: str, password: str) -> None:
    if not _is_supabase_pooler_host(host):
        return
    if user == "postgres" or "." not in user:
        raise ValueError(
            "Supabase pooler needs DB_USER=postgres.<project_ref> (e.g. postgres.dsvrpmwujvkeqpuplurh), "
            "not bare 'postgres'. Copy it from Dashboard → Connect → Session pooler or Transaction pooler."
        )
    if not password or password.strip() in ("YOUR_PASSWORD", "your_password", "[YOUR-PASSWORD]"):
        raise ValueError(
            "Set DB_PASSWORD in .env to your real database password "
            "(Dashboard → Project Settings → Database → Database password)."
        )


def _force_ipv4_for_host(host: str) -> bool:
    if _is_supabase_pooler_host(host):
        return False
    v = os.environ.get("DB_FORCE_IPV4", "").strip().lower()
    if v in ("0", "false", "no"):
        return False
    if v in ("1", "true", "yes"):
        return True
    return host.startswith("db.") and "supabase.co" in host


def _url_with_hostaddr(url: str) -> str:
    normalized = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    parsed = urlparse(normalized)
    hostname = parsed.hostname or ""
    if not hostname or hostname in ("localhost", "127.0.0.1"):
        return url
    if not _force_ipv4_for_host(hostname):
        return url
    ip = _first_ipv4(hostname)
    if not ip:
        return url
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "hostaddr" in q:
        return url
    q["hostaddr"] = ip
    new_query = urlencode(q)
    rebuilt = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "", "", new_query, "")
    )
    return rebuilt.replace("postgresql://", "postgresql+psycopg2://", 1)


def build_database_url() -> str:
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        url = _url_with_hostaddr(explicit)
        norm = url.replace("postgresql+psycopg2://", "postgresql://", 1)
        p = urlparse(norm)
        _validate_pooler_credentials(
            (p.hostname or "").lower(),
            p.username or "",
            p.password or "",
        )
        return url

    host = os.environ.get("DB_HOST", "").strip()
    if not host:
        user = os.environ.get("DB_USER", "").strip()
        if user.startswith("postgres.") and user != "postgres":
            raise ValueError(
                "DB_HOST is empty but DB_USER looks like a Supabase pooler user (postgres.<project_ref>). "
                "Set DB_HOST to the Session pooler hostname from Dashboard → Connect → Session pooler "
                "(e.g. aws-0-<region>.pooler.supabase.com)."
            )
        return _DEFAULT_LOCAL

    port = os.environ.get("DB_PORT", "5432").strip()
    name = os.environ.get("DB_NAME", "postgres").strip()
    user = os.environ.get("DB_USER", "postgres").strip()
    password = os.environ.get("DB_PASSWORD", "")

    _validate_pooler_credentials(host.lower(), user, password)

    user_q = quote_plus(user)
    password_q = quote_plus(password)
    name_q = quote_plus(name)
    url = f"postgresql+psycopg2://{user_q}:{password_q}@{host}:{port}/{name_q}"

    query_parts: list[str] = []
    sslmode = os.environ.get("DB_SSLMODE", "").strip()
    if sslmode:
        query_parts.append(f"sslmode={quote_plus(sslmode)}")
    if _force_ipv4_for_host(host):
        ip = _first_ipv4(host)
        if ip:
            query_parts.append(f"hostaddr={quote_plus(ip)}")

    if query_parts:
        url += "?" + "&".join(query_parts)

    return url


DATABASE_URL = build_database_url()


def _pooler_connect_args() -> dict:
    normalized = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    if "pooler.supabase.com" in host or parsed.port == 6543:
        return {"prepare_threshold": None}
    return {}


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_pooler_connect_args(),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_schema(engine) -> None:
    ddl = [
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE last_scrape ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE last_scrape ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
