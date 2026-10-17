"""FastAPI application factory."""

# Release 1 (Commercial & Capacity Control Plane). First CD deploy trigger.
from fastapi import FastAPI

from neocloud.core.config import get_settings
from neocloud.core.logging import configure_logging, get_logger
from neocloud.core.middleware import CorrelationIdMiddleware

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="NeoCloud GPU Control Platform - Release 1 (Commercial & Capacity Control Plane)",
    )

    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    _register_routers(app, settings.api_v1_prefix)

    logger.info("app_initialized", env=settings.app_env)
    return app


def _register_routers(app: FastAPI, prefix: str) -> None:
    """Register domain routers. Imported lazily to avoid heavy import at module load."""
    from neocloud.domains.capacity.router import router as capacity_router
    from neocloud.domains.catalog.router import router as catalog_router
    from neocloud.domains.contracts.router import router as contracts_router
    from neocloud.domains.customers.router import router as customers_router
    from neocloud.domains.dashboards.router import router as dashboards_router
    from neocloud.domains.documents.router import router as documents_router
    from neocloud.domains.inventory.router import router as inventory_router
    from neocloud.domains.reservations.router import router as reservations_router
    from neocloud.domains.sales.router import router as sales_router

    for r in (
        customers_router,
        catalog_router,
        inventory_router,
        capacity_router,
        sales_router,
        contracts_router,
        reservations_router,
        documents_router,
        dashboards_router,
    ):
        app.include_router(r, prefix=prefix)


app = create_app()
