"""Async SQLAlchemy engine and session management.

Database URL resolution order:
1. settings.database_url (explicit, e.g. local SQLite for tests)
2. Aurora credentials fetched from Secrets Manager + aurora_host
"""

import json
from collections.abc import AsyncGenerator

import boto3
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from neocloud.core.config import Settings, get_settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)


def _resolve_database_url(settings: Settings) -> str:
    if settings.database_url:
        return settings.database_url

    if not (settings.aurora_secret_arn and settings.aurora_host):
        raise RuntimeError(
            "No database configuration: set DATABASE_URL, or both "
            "AURORA_SECRET_ARN and AURORA_HOST."
        )

    client = boto3.client("secretsmanager", region_name=settings.aws_region)
    secret = client.get_secret_value(SecretId=settings.aurora_secret_arn)
    creds = json.loads(secret["SecretString"])

    user = creds["username"]
    password = creds["password"]
    return (
        f"postgresql+asyncpg://{user}:{password}@"
        f"{settings.aurora_host}:{settings.aurora_port}/{settings.aurora_database}"
    )


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        url = _resolve_database_url(settings)
        _engine = create_async_engine(
            url,
            echo=settings.db_echo,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("database_engine_initialized")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional session."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
