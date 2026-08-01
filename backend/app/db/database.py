"""SQLAlchemy engine and session factory.

The connection string and pool tuning come from the centralized settings
. The historical zero-config SQLite default is preserved when
``DATABASE_URL`` is unset, so every existing dev/test flow keeps working; set
``DATABASE_URL`` to a PostgreSQL DSN (plus the ``DB_POOL_*`` knobs) for
staging/production. ``DATABASE_URL`` remains importable for Alembic.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from backend.app.core.settings import get_settings

_settings = get_settings()

# Exposed for Alembic (backend/alembic/env.py) and backward compatibility.
DATABASE_URL = _settings.database_url

# Pool tuning + connect args are derived from the profile: SQLite gets the
# thread guard only; real DB servers get sized connection pooling with
# pre-ping (drops dead connections) and recycling.
engine = create_engine(
    DATABASE_URL,
    **_settings.sqlalchemy_engine_kwargs,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# Dependency
def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
