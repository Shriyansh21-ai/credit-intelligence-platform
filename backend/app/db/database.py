import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Phase 8 (M11): the connection string is environment-overridable for cloud
# deployments (Postgres, etc.). The historical SQLite default is unchanged when
# ``DATABASE_URL`` is not set, so every existing dev/test flow keeps working.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./credit_ai.db")

# ``check_same_thread`` is a SQLite-only connect arg; omit it for other engines.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependency
def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()