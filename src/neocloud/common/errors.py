from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base domain error."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} not found: {identifier}", code="NOT_FOUND")


class ConflictError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="CONFLICT")


class CapacityExceededError(DomainError):
    def __init__(self, requested: int, available: int, gpu_model: str, region: str):
        super().__init__(
            f"Capacity exceeded for {gpu_model} in {region}: requested={requested}, available={available}",
            code="CAPACITY_EXCEEDED",
        )
        self.requested = requested
        self.available = available


class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_map = {
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "CONFLICT": status.HTTP_409_CONFLICT,
        "CAPACITY_EXCEEDED": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    return JSONResponse(
        status_code=status_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        content={"error": {"code": exc.code, "message": exc.message}},
    )
