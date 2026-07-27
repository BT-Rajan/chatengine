"""
schema.py — introspects the connected database and renders a compact
text description the LLM can use to write SQL, plus a couple of sample
rows per table so it understands the shape of the actual content (not
just column names) — the same idea as the original app handing the model
formatted lines of live inventory/orders data, generalized to any schema.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass
class TableInfo:
    name: str
    columns: list[dict[str, Any]] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[dict[str, Any]] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int | None = None


def introspect_schema(
    engine: Engine,
    sample_rows_per_table: int = 3,
    include_row_counts: bool = True,
    only_tables: list[str] | None = None,
) -> list[TableInfo]:
    inspector = inspect(engine)
    tables = only_tables or inspector.get_table_names()
    result: list[TableInfo] = []

    with engine.connect() as conn:
        for table_name in tables:
            try:
                cols = inspector.get_columns(table_name)
                pk = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
                fks = inspector.get_foreign_keys(table_name)
            except Exception:
                # Skip anything we can't introspect (views with odd permissions, etc.)
                continue

            info = TableInfo(
                name=table_name,
                columns=[{"name": c["name"], "type": str(c["type"])} for c in cols],
                primary_key=pk or [],
                foreign_keys=[
                    {
                        "columns": fk.get("constrained_columns", []),
                        "refers_to": fk.get("referred_table"),
                        "refers_to_columns": fk.get("referred_columns", []),
                    }
                    for fk in fks
                ],
            )

            if include_row_counts:
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar()
                    info.row_count = int(count) if count is not None else None
                except Exception:
                    info.row_count = None

            if sample_rows_per_table > 0:
                try:
                    rows = conn.execute(
                        text(f"SELECT * FROM `{table_name}` LIMIT :n"),
                        {"n": sample_rows_per_table},
                    ).mappings().all()
                    info.sample_rows = [dict(r) for r in rows]
                except Exception:
                    info.sample_rows = []

            result.append(info)

    return result


def render_schema_for_prompt(tables: list[TableInfo]) -> str:
    """Turns introspected schema into compact text for the system prompt."""
    lines: list[str] = []
    for t in tables:
        col_desc = ", ".join(f"{c['name']} ({c['type']})" for c in t.columns)
        pk_desc = f" | primary key: {', '.join(t.primary_key)}" if t.primary_key else ""
        row_desc = f" | ~{t.row_count} rows" if t.row_count is not None else ""
        lines.append(f"TABLE {t.name}{row_desc}{pk_desc}\n  columns: {col_desc}")

        for fk in t.foreign_keys:
            lines.append(
                f"  foreign key: {', '.join(fk['columns'])} -> "
                f"{fk['refers_to']}({', '.join(fk['refers_to_columns'])})"
            )

        if t.sample_rows:
            lines.append(f"  sample rows: {t.sample_rows}")

        lines.append("")

    return "\n".join(lines)
