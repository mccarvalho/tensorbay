"""Alembic environment using the application's metadata and DB URL."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from neocloud.core.config import get_settings
from neocloud.db.base import Base
from neocloud.db.session import _resolve_database_url

# Import every domain's models so they register on Base.metadata.
from neocloud.audit import service as _audit  # noqa: F401
from neocloud.domains.customers import models as _customers  # noqa: F401
from neocloud.domains.catalog import models as _catalog  # noqa: F401
from neocloud.domains.inventory import models as _inventory  # noqa: F401
from neocloud.domains.capacity import models as _capacity  # noqa: F401
from neocloud.domains.suppliers import models as _suppliers  # noqa: F401
from neocloud.domains.sales import models as _sales  # noqa: F401
from neocloud.domains.contracts import models as _contracts  # noqa: F401
from neocloud.domains.reservations import models as _reservations  # noqa: F401
from neocloud.domains.documents import models as _documents  # noqa: F401
from neocloud.domains.economics import models as _economics  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    return _resolve_database_url(get_settings())


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
