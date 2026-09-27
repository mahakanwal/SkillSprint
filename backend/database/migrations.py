"""
database/migrations.py

Tiny, idempotent schema upgrader run at startup (after create_all).

SQLAlchemy's create_all() creates NEW tables but never adds new columns to
tables that already exist. Instead of asking you to drop the database, this
adds any column that is defined on a model but missing in the live table.
It never drops or alters existing columns, so existing data is untouched.
Works on PostgreSQL and SQLite.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def upgrade_schema(engine: Engine, base) -> list[str]:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added = []

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all already built it with every column
            live_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_cols:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}'))
                added.append(f"{table.name}.{column.name}")

    return added
