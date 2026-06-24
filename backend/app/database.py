from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DATABASE_URL_FROM_ENV = bool(os.getenv("DATABASE_URL"))
DEFAULT_DATABASE_URL = "sqlite:///./yakson_local.db"
DATABASE_URL = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "" if IS_SQLITE else "yakson").strip() or None
DATABASE_AUTO_CREATE = _bool_env("DATABASE_AUTO_CREATE", default=IS_SQLITE)
DATABASE_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "5"))


class Base(DeclarativeBase):
    metadata = MetaData(schema=DATABASE_SCHEMA)


connect_args = {"check_same_thread": False} if IS_SQLITE else {"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if not IS_SQLITE:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def qualified_table(table_name: str) -> str:
    if DATABASE_SCHEMA:
        return f"{DATABASE_SCHEMA}.{table_name}"
    return table_name


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_info() -> dict[str, object]:
    url = make_url(DATABASE_URL)
    return {
        "driver": url.drivername,
        "databaseName": url.database,
        "schema": DATABASE_SCHEMA,
        "autoCreate": DATABASE_AUTO_CREATE,
        "usingDefaultSqlite": IS_SQLITE and not DATABASE_URL_FROM_ENV,
    }


def initialize_database() -> None:
    if not DATABASE_AUTO_CREATE:
        return

    if DATABASE_SCHEMA and not IS_SQLITE:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))

    Base.metadata.create_all(bind=engine)
