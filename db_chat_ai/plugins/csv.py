"""
plugins/csv.py — the "csv" plugin.

Loads .csv files (from FILES in ai-conf.py) as real, queryable tables in
an in-memory SQLite engine (unchanged logic, now living in
sources/csv_tables.py) and exposes them the same way the sql plugin
exposes a real database — same schema-introspection, same read-only
validation and execution path.
"""

from sqlalchemy import text as sql_text

from ..interfaces.plugin import Plugin
from ..schema import introspect_schema, render_schema_for_prompt
from ..sources.csv_tables import build_csv_engine
from ..sql_guard import enforce_row_limit, validate_select_only


class CSVPlugin(Plugin):
    name = "csv"

    def __init__(self, config):
        self.paths = config.files
        self.sample_rows_per_table = config.sample_rows_per_table
        self.max_rows = config.max_rows
        self.engine, self.tables = build_csv_engine(self.paths)
        self._schema_cache: str | None = None

    @property
    def kind(self) -> str:
        return "sql"

    @property
    def is_active(self) -> bool:
        """True only if at least one .csv file was actually found/loaded —
        lets the plugin loader skip it cleanly when 'csv' is enabled but
        FILES contains no .csv files."""
        return self.engine is not None

    def describe(self) -> str:
        if not self.is_active:
            return ""
        if self._schema_cache is None:
            tables = introspect_schema(self.engine, sample_rows_per_table=self.sample_rows_per_table)
            self._schema_cache = render_schema_for_prompt(tables) if tables else ""
        return self._schema_cache

    def search(self, query: str) -> list[dict]:
        if not self.is_active:
            return []
        safe_sql = validate_select_only(query)
        safe_sql = enforce_row_limit(safe_sql, self.max_rows)
        with self.engine.connect() as conn:
            result = conn.execute(sql_text(safe_sql)).mappings().all()
            return [dict(r) for r in result]

    def refresh(self) -> None:
        self.engine, self.tables = build_csv_engine(self.paths)
        self._schema_cache = None
