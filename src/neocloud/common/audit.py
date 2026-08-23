"""
Audit trail middleware for tracking API operations.
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request, Response
from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from starlette.middleware.base import BaseHTTPMiddleware

from .database import Base
from .events import DomainEvent


class AuditLog(Base):
    """Audit log model for tracking operations."""
    
    __tablename__ = "audit_logs"
    
    event_id: str = Column(String, unique=True, index=True, nullable=False)
    user_id: Optional[str] = Column(String, index=True)
    customer_id: Optional[str] = Column(String, index=True)
    action: str = Column(String, nullable=False)
    resource_type: str = Column(String, nullable=False)
    resource_id: Optional[str] = Column(String, index=True)
    request_method: str = Column(String, nullable=False)
    request_path: str = Column(String, nullable=False)
    request_body: Optional[Dict[str, Any]] = Column(JSON)
    response_status: int = Column(String, nullable=False)
    ip_address: str = Column(String)
    user_agent: str = Column(String)
    session_id: Optional[str] = Column(String)
    metadata: Optional[Dict[str, Any]] = Column(JSON)
    timestamp: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for auditing API requests and responses."""
    
    # Paths to exclude from audit logging
    EXCLUDE_PATHS = {
        "/docs",
        "/redoc", 
        "/openapi.json",
        "/health",
    }
    
    # Methods to exclude from audit logging
    EXCLUDE_METHODS = {"GET", "OPTIONS", "HEAD"}
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log audit trail."""
        # Skip audit for excluded paths or methods
        if (request.url.path in self.EXCLUDE_PATHS or 
            request.method in self.EXCLUDE_METHODS):
            return await call_next(request)
        
        # Capture request details
        start_time = datetime.utcnow()
        event_id = str(uuid.uuid4())
        
        # Extract user info from request state (set by AuthMiddleware)
        user_id = getattr(request.state, 'user_id', None)
        customer_id = getattr(request.state, 'customer_id', None)
        
        # Read request body
        request_body = None
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if body:
                try:
                    request_body = json.loads(body.decode())
                    # Remove sensitive fields
                    if isinstance(request_body, dict):
                        request_body = self._sanitize_request_body(request_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    request_body = {"_raw": body.decode('utf-8', errors='ignore')}
        
        # Get client info
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Determine resource info from path
        resource_type, resource_id = self._extract_resource_info(request.url.path)
        
        # Create audit log entry
        audit_data = {
            "event_id": event_id,
            "user_id": user_id,
            "customer_id": customer_id,
            "action": self._determine_action(request.method, request.url.path),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_method": request.method,
            "request_path": request.url.path,
            "request_body": request_body,
            "response_status": response.status_code,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": {
                "processing_time_seconds": processing_time,
                "query_params": dict(request.query_params),
                "request_size_bytes": len(await request.body()) if request.method in {"POST", "PUT", "PATCH"} else 0,
            },
            "timestamp": start_time
        }
        
        # Publish audit event (async, non-blocking)
        try:
            event = DomainEvent(
                event_type="audit.api_request",
                source="neocloud.audit",
                data=audit_data
            )
            await event.publish()
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to publish audit event: {e}")
        
        return response
    
    def _sanitize_request_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from request body."""
        sensitive_fields = {"password", "token", "secret", "key", "credential"}
        sanitized = body.copy()
        
        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                sanitized[key] = "***REDACTED***"
        
        return sanitized
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if hasattr(request.client, 'host'):
            return request.client.host
        
        return "unknown"
    
    def _extract_resource_info(self, path: str) -> tuple[str, Optional[str]]:
        """Extract resource type and ID from request path."""
        parts = [p for p in path.split("/") if p]
        
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
            resource_type = parts[2]
            resource_id = parts[3] if len(parts) > 3 else None
            return resource_type, resource_id
        
        return "unknown", None
    
    def _determine_action(self, method: str, path: str) -> str:
        """Determine the action being performed."""
        method_actions = {
            "POST": "create",
            "PUT": "update", 
            "PATCH": "update",
            "DELETE": "delete",
            "GET": "read"
        }
        
        base_action = method_actions.get(method, "unknown")
        
        # Add path context for more specific actions
        if "login" in path:
            return "login"
        elif "logout" in path:
            return "logout"
        elif "password" in path:
            return "change_password"
        
        return base_action