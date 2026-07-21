"""Alembic environment.

Wires migrations to the application's SQLAlchemy metadata and database URL so
``alembic revision --autogenerate`` sees every ORM model. Add new models to
the import block below and they will be picked up automatically.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the project root importable (so `backend.app...` resolves) regardless
# of where alembic is invoked from.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.db.database import Base, DATABASE_URL  # noqa: E402

# Import every model module so its table registers on Base.metadata.
from backend.app.models import user  # noqa: E402,F401
from backend.app.models import prediction  # noqa: E402,F401
from backend.app.models import fraud  # noqa: E402,F401
from backend.app.models import portfolio  # noqa: E402,F401
from backend.app.models import enterprise_assessment  # noqa: E402,F401
from backend.app.models import document  # noqa: E402,F401
from backend.app.models import financial_analysis  # noqa: E402,F401

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite lacks native ALTER; batch mode emulates it
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
