"""
sql_guard.py — validates that LLM-generated SQL is a single, read-only
SELECT before it's ever executed. The original app never let the LLM
touch the database directly (it only proposed an "action" that was then
matched against real catalog names and applied through existing update
functions); this library keeps the same principle: the LLM proposes a
query, this guard is the gate before anything runs.
"""

import re

_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "replace", "merge", "call", "exec", "execute",
    "attach", "pragma", "into outfile", "load_file",
)


class UnsafeSQLError(ValueError):
    pass


def validate_select_only(sql: str) -> str:
    """Raises UnsafeSQLError if sql is anything other than one read-only
    SELECT statement. Returns the (trimmed) sql if it passes."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL.")

    cleaned = sql.strip().rstrip(";").strip()

    # Reject multiple statements chained with ';'.
    if ";" in cleaned:
        raise UnsafeSQLError("Multiple statements are not allowed.")

    lowered = cleaned.lower()

    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise UnsafeSQLError("Only SELECT (or WITH ... SELECT) statements are allowed.")

    for kw in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            raise UnsafeSQLError(f"Query contains a disallowed keyword: '{kw}'.")

    return cleaned


def enforce_row_limit(sql: str, max_rows: int) -> str:
    """Appends a LIMIT if the query doesn't already have one, so a broad
    question can't pull an entire large table into memory/back to the LLM."""
    if re.search(r"\blimit\s+\d+\s*$", sql.strip(), re.IGNORECASE):
        return sql
    return f"{sql.rstrip()} LIMIT {max_rows}"
