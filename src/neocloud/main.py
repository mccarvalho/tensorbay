from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from neocloud.common.config import settings
from neocloud.common.errors import DomainError, domain_error_handler
from neocloud.customers.router import router as customers_router
from neocloud.catalog.router import router as catalog_router
from neocloud.sales.router import router as sales_router
from neocloud.contracts.router import router as contracts_router
from neocloud.inventory.router import router as inventory_router
from neocloud.capacity.router import router as capacity_router
from neocloud.reservations.router import router as reservations_router
from neocloud.allocations.router import router as allocations_router
from neocloud.iam.router import router as iam_router
from neocloud.audit.router import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load secrets from AWS Secrets Manager (production/staging only)
    from neocloud.common.secrets import load_secrets_to_env
    load_secrets_to_env(
        env=settings.app_env,
        region=settings.aws_region,
    )

    # Configure structured logging
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    yield
    # Shutdown


app = FastAPI(
    title="NeoCloud GPU Control Platform",
    description="Commercial & Infrastructure Control Plane for GPU NeoCloud",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(DomainError, domain_error_handler)

# Routers
app.include_router(customers_router, prefix="/v1/customers", tags=["Customers"])
app.include_router(catalog_router, prefix="/v1/catalog", tags=["Catalog & Pricing"])
app.include_router(sales_router, prefix="/v1/sales", tags=["Sales"])
app.include_router(contracts_router, prefix="/v1/contracts", tags=["Contracts"])
app.include_router(inventory_router, prefix="/v1/inventory", tags=["Inventory"])
app.include_router(capacity_router, prefix="/v1/capacity", tags=["Capacity"])
app.include_router(reservations_router, prefix="/v1/reservations", tags=["Reservations"])
app.include_router(allocations_router, prefix="/v1/allocations", tags=["Allocations"])
app.include_router(iam_router, prefix="/v1/iam", tags=["IAM"])
app.include_router(audit_router, prefix="/v1/audit", tags=["Audit"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
