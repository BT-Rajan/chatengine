"""
csv_tables.py — loads .csv files as real, queryable tables in an in-memory
SQLite database, so questions about CSV content go through the exact same
NL -> SQL -> validated-execution -> plain-language-answer path as the "db"
source, instead of being treated as unstructured text.

(.md / .txt files and web pages go through documents.py's relevance-search
path instead, since they're prose, not tables.)
"""

import os
import re

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


def _sanitize_table_name(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_")
    return name or "csv_table"


def _expand_csv_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".csv"):
                        out.append(os.path.join(root, f))
        elif p.lower().endswith(".csv"):
            out.append(p)
    return out


def build_csv_engine(paths: list[str]) -> tuple[Engine | None, dict[str, str]]:
    """Loads every .csv found in `paths` (files or folders) into its own
    table in a shared in-memory SQLite engine. Returns (engine, {table_name:
    source_path}); engine is None if no CSVs were found/loaded or pandas
    isn't installed."""
    csv_paths = _expand_csv_paths(paths)
    if not csv_paths:
        return None, {}
    if pd is None:
        raise RuntimeError(
            "pandas is required to load .csv files as queryable tables. "
            "Install it with `pip install pandas`."
        )

    # StaticPool + check_same_thread=False keeps ONE underlying in-memory
    # SQLite connection alive for the engine's lifetime — without this,
    # each new connection would see a fresh, empty in-memory database and
    # every table we just loaded would vanish before it could be queried.
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    table_sources: dict[str, str] = {}

    with engine.begin() as conn:
        used_names: set[str] = set()
        for path in csv_paths:
            try:
                df = pd.read_csv(path)
            except Exception:
                continue
            table_name = _sanitize_table_name(path)
            base_name = table_name
            i = 2
            while table_name in used_names:
                table_name = f"{base_name}_{i}"
                i += 1
            used_names.add(table_name)
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            table_sources[table_name] = path

    return engine, table_sources
