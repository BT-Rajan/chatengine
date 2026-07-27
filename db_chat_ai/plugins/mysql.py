"""
plugins/mysql.py — the "sql" plugin.

Named to match the reference plugin listing (mysql.py), but — same as
before this refactor — actually works with any SQLAlchemy-supported
database via DB_URL (MySQL, Postgres, SQLite, ...); "mysql" here is a
label, not a restriction.

This is a thin wrapper: all the actual logic (schema introspection,
read-only validation, execution) is unchanged from before this refactor,
living in connector.py / schema.py / sql_guard.py. The plugin just gives
the chat engine a uniform way to reach it.
"""

from sqlalchemy import text as sql_text

from ..connector import get_engine
from ..interfaces.plugin import Plugin
from ..schema import introspect_schema, render_schema_for_prompt
from ..sql_guard import enforce_row_limit, validate_select_only


class SQLPlugin(Plugin):
    name = "sql"

    def __init__(self, config):
        self.engine = get_engine(config.db_url)
        self.sample_rows_per_table = config.sample_rows_per_table
        self.max_rows = config.max_rows
        self._schema_cache: str | None = None

    @property
    def kind(self) -> str:
        return "sql"

    def describe(self) -> str:
        if self._schema_cache is None:
            tables = introspect_schema(self.engine, sample_rows_per_table=self.sample_rows_per_table)
            self._schema_cache = render_schema_for_prompt(tables) if tables else ""
        return self._schema_cache

    def search(self, query: str) -> list[dict]:
        """query is a SQL string. Validates it's read-only, enforces a row
        limit, executes it, and returns the rows. Raises UnsafeSQLError /
        the underlying DB exception on failure — the chat engine decides
        how to surface that to the user."""
        safe_sql = validate_select_only(query)
        safe_sql = enforce_row_limit(safe_sql, self.max_rows)
        with self.engine.connect() as conn:
            result = conn.execute(sql_text(safe_sql)).mappings().all()
            return [dict(r) for r in result]

    def refresh(self) -> None:
        self._schema_cache = None
