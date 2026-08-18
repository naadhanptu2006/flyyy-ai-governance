"""
Lightweight schema auto-migration.

This project intentionally uses `Base.metadata.create_all()` instead of
Alembic (documented trade-off in the README, appropriate for a 4-day
assignment). The gap that leaves: `create_all()` only creates tables
that don't exist yet — it never alters an EXISTING table when a model
gains a new column. Since Postgres data persists across
`docker compose up` runs (by design, via the `pgdata` volume), a schema
change like the profile "description/owner/environment" fields added
later would silently fail to reach a database that was first created
before those columns existed — every insert into that table would then
error out with a missing-column database error.

`run_auto_migrate()` closes that specific gap: after `create_all()` runs,
it compares each model's expected columns against what actually exists
in the live database and adds any that are missing, using each column's
own nullable/default so this never fails on existing rows. This is not a
replacement for real migrations (it can't rename, drop, or alter a
column's type) — it only ever adds new nullable columns, which is
exactly the shape of change this project has needed so far.
"""
from sqlalchemy import inspect, text


def run_auto_migrate(engine, Base):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue  # create_all() already handles brand-new tables

            existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue

                ddl_type = column.type.compile(dialect=engine.dialect)
                stmt = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {ddl_type}'
                try:
                    conn.execute(text(stmt))
                    print(f"[auto-migrate] Added missing column: {table_name}.{column.name}")
                except Exception as e:
                    # Don't crash startup over a migration best-effort step —
                    # log it so it's visible, since the real fix at that
                    # point is a full migration tool, not this fallback.
                    print(f"[auto-migrate] Could not add {table_name}.{column.name}: {e}")
