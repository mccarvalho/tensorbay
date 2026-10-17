"""Shared pytest fixtures for the NeoCloud test suite.

Environment is configured BEFORE importing the application so that
`get_settings()` (which is lru_cached) picks up the test configuration:

* AUTH_ENABLED=false            -> auth is bypassed with a stub SUPER_ADMIN user
* DATABASE_URL=sqlite in-memory -> no Aurora / Secrets Manager dependency
* DOCUMENTS_BUCKET unset        -> document service skips S3 uploads

A single in-memory SQLite engine backed by a StaticPool is shared between the
table-creation fixture and the FastAPI request handlers, so rows created in a
test are visible to the ASGI app (a plain ``:memory:`` URL would otherwise give
each connection its own private database).
"""

import os

# --- Configure environment BEFORE importing anything from the app ----------
os.environ["AUTH_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.pop("DOCUMENTS_BUCKET", None)

from collections.abc import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

# Register metadata: importing every domain models module ensures all tables
# are attached to Base.metadata before create_all runs.
from neocloud.audit import service as _audit_service  # noqa: E402,F401
from neocloud.db import session as db_session  # noqa: E402
from neocloud.db.base import Base  # noqa: E402
from neocloud.domains.capacity import models as _capacity_models  # noqa: E402,F401
from neocloud.domains.catalog import models as _catalog_models  # noqa: E402,F401
from neocloud.domains.contracts import models as _contracts_models  # noqa: E402,F401
from neocloud.domains.customers import models as _customers_models  # noqa: E402,F401
from neocloud.domains.documents import models as _documents_models  # noqa: E402,F401
from neocloud.domains.inventory import models as _inventory_models  # noqa: E402,F401
from neocloud.domains.reservations import models as _reservations_models  # noqa: E402,F401
from neocloud.domains.sales import models as _sales_models  # noqa: E402,F401

# One shared engine for the whole test session.
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionmaker = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def _db_schema() -> AsyncGenerator[None, None]:
    """Create all tables on the shared engine before each test, drop after.

    The app's lazy engine/sessionmaker globals are redirected to the shared
    test engine so request handlers and test setup hit the same database.
    """
    # Redirect the app's module-level engine + sessionmaker to our test engine.
    db_session._engine = _test_engine
    db_session._sessionmaker = _TestSessionmaker

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def session() -> AsyncGenerator[AsyncSession, None]:
    """A direct AsyncSession for seeding/inspecting data inside tests."""
    async with _TestSessionmaker() as s:
        yield s
        await s.commit()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient bound to the FastAPI app via ASGITransport."""
    from neocloud.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac
