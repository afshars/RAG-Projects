import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

os.makedirs("data", exist_ok=True)

# This app has no accounts or login — everything runs as a single local
# workspace. This fixed id is used only to namespace stored data (DB rows,
# FAISS/BM25 index files) internally; it has no relation to authentication.
LOCAL_WORKSPACE_ID = "local"

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app import models  # noqa: F401  (ensure models are registered)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(sync_conn):
    """create_all only creates tables that don't exist yet — it never adds
    a column to a table that's already there. For a small local-first app
    like this (no Alembic), this sync-conn helper does the minimum needed:
    for every mapped column not present in the actual SQLite table, issue
    an ALTER TABLE ... ADD COLUMN. Safe to run on every startup — already
    all-present tables are a no-op."""
    import sqlalchemy as sa

    inspector = sa.inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # brand-new table — create_all already handled it
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            col_type = column.type.compile(dialect=sync_conn.dialect)
            default_clause = ""
            if column.default is not None and getattr(column.default, "is_scalar", False):
                value = column.default.arg
                if isinstance(value, str):
                    default_clause = f" DEFAULT '{value}'"
                elif isinstance(value, bool):
                    default_clause = f" DEFAULT {1 if value else 0}"
                elif isinstance(value, (int, float)):
                    default_clause = f" DEFAULT {value}"
            sync_conn.execute(
                sa.text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" '
                    f"{col_type}{default_clause}"
                )
            )
