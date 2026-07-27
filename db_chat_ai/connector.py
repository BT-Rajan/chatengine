"""
connector.py — generic database connection for db-chat-ai.

The original JDK app hardcoded a pymysql connection to one MySQL schema.
This library talks to any SQLAlchemy-supported database (MySQL, Postgres,
SQLite, MSSQL, ...) so the same chat engine can be pointed at a different
project's DB just by changing a connection string.

Config precedence: DB_URL env var > individual DB_* env vars (same names
as the original app: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD) built
into a MySQL URL for drop-in compatibility with that project.
"""

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _build_url_from_parts() -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "")
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    charset = os.environ.get("DB_CHARSET", "utf8mb4")
    if not name:
        raise RuntimeError(
            "No DB_URL and no DB_NAME set. Set DB_URL (e.g. "
            "'postgresql://user:pass@host:5432/dbname' or 'sqlite:///path/to.db'), "
            "or set DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD for MySQL."
        )
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset={charset}"


def get_database_url(configured_url: str = "") -> str:
    """Precedence: an explicit DB_URL set in ai-conf.py > DB_URL env var >
    the individual DB_HOST/DB_NAME/... env vars (MySQL, for continuity with
    the original app's settings)."""
    return configured_url or os.environ.get("DB_URL") or _build_url_from_parts()


@lru_cache(maxsize=8)
def get_engine(configured_url: str = "") -> Engine:
    """Read-only-intent engine. Actual write prevention is enforced at the
    SQL-safety layer (sql_guard.py), not here — but using a DB user that only
    has SELECT granted is strongly recommended as a second layer of defense."""
    url = get_database_url(configured_url)
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def reset_engine_cache() -> None:
    """Useful for tests or after changing env vars at runtime."""
    get_engine.cache_clear()
