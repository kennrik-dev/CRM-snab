from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, event, engine_from_config, pool

from alembic import context

from app.backup import run_backup
from app.config import settings
from app.db import Base
from app import models  # noqa: register models on Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def _fk_pragma_on_connect(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = f"sqlite:///{settings.DB_PATH}"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = f"sqlite:///{settings.DB_PATH}"
    connectable = create_engine(
        url,
        connect_args={"check_same_thread": False},
    )

    event.listen(connectable, "connect", _fk_pragma_on_connect)

    # §3: обязательный бэкап перед миграциями. Кладём рядом с crm.db/backups.
    _backup_dir = str(Path(settings.DB_PATH).resolve().parent / "backups")
    run_backup(settings.DB_PATH, _backup_dir, keep=14)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
