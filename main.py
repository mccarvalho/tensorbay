"""
NeoCloud GPU Control Platform - Main Application
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .common.config import get_settings
from .common.database import init_db
from .common.errors import http_exception_handler, validation_exception_handler
from .common.auth import AuthMiddleware
from .common.audit import AuditMiddleware

# Import routers
from .customers.router import router as customers_router
from .catalog.router import router as catalog_router
from .sales.router import router as sales_router
from .contracts.router import router as contracts_router
from .inventory.router import router as inventory_router
from .capacity.router import router as capacity_router
from .reservations.router import router as reservations_router
from .allocations.router import router as allocations_router
from .iam.router import router as iam_router
from .audit.router import router as audit_router
from .dashboards.router import router as dashboards_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Initialize database
    await init_db()
    yield
    # Cleanup if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="NeoCloud GPU Control Platform",
        description="Production-ready GPU infrastructure management platform",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AuditMiddleware)

    # Add exception handlers
    app.add_exception_handler(Exception, http_exception_handler)
    app.add_exception_handler(ValueError, validation_exception_handler)

    # Include routers
    app.include_router(customers_router, prefix="/api/v1/customers", tags=["Customers"])
    app.include_router(catalog_router, prefix="/api/v1/catalog", tags=["Catalog"])
    app.include_router(sales_router, prefix="/api/v1/sales", tags=["Sales"])
    app.include_router(contracts_router, prefix="/api/v1/contracts", tags=["Contracts"])
    app.include_router(inventory_router, prefix="/api/v1/inventory", tags=["Inventory"])
    app.include_router(capacity_router, prefix="/api/v1/capacity", tags=["Capacity"])
    app.include_router(reservations_router, prefix="/api/v1/reservations", tags=["Reservations"])
    app.include_router(allocations_router, prefix="/api/v1/allocations", tags=["Allocations"])
    app.include_router(iam_router, prefix="/api/v1/iam", tags=["IAM"])
    app.include_router(audit_router, prefix="/api/v1/audit", tags=["Audit"])
    app.include_router(dashboards_router, prefix="/api/v1/dashboards", tags=["Dashboards"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "1.0.0"}

    return app


# Create the app instance
app = create_app()