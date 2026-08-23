"""
Customer domain specific exceptions.
"""
from typing import Any, Dict, Optional

from ..common.errors import NeoCloudException


class CustomerException(NeoCloudException):
    """Base exception for customer domain."""
    pass


class CustomerNotFound(CustomerException):
    """Exception raised when customer is not found."""
    
    def __init__(self, customer_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Customer not found: {customer_id}",
            error_code="CUSTOMER_NOT_FOUND",
            details=details or {"customer_id": customer_id}
        )


class DuplicateCustomerEmail(CustomerException):
    """Exception raised when trying to create customer with existing email."""
    
    def __init__(self, email: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Customer with email '{email}' already exists",
            error_code="DUPLICATE_CUSTOMER_EMAIL",
            details=details or {"email": email}
        )


class InvalidCustomerStatus(CustomerException):
    """Exception raised for invalid customer status transitions."""
    
    def __init__(
        self,
        current_status: str,
        requested_status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Invalid status transition from '{current_status}' to '{requested_status}'",
            error_code="INVALID_CUSTOMER_STATUS_TRANSITION",
            details=details or {
                "current_status": current_status,
                "requested_status": requested_status
            }
        )


class CustomerContactNotFound(CustomerException):
    """Exception raised when customer contact is not found."""
    
    def __init__(self, contact_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Customer contact not found: {contact_id}",
            error_code="CUSTOMER_CONTACT_NOT_FOUND",
            details=details or {"contact_id": contact_id}
        )


class CustomerPaymentMethodNotFound(CustomerException):
    """Exception raised when customer payment method is not found."""
    
    def __init__(self, payment_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Customer payment method not found: {payment_id}",
            error_code="CUSTOMER_PAYMENT_METHOD_NOT_FOUND",
            details=details or {"payment_id": payment_id}
        )


class CustomerValidationError(CustomerException):
    """Exception raised for customer data validation errors."""
    
    def __init__(self, message: str, field: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CUSTOMER_VALIDATION_ERROR",
            details=details or {"field": field}
        )