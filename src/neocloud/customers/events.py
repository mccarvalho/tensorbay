"""
Customer domain events.
"""
from typing import Dict, List, Optional

from ..common.events import DomainEvent


class CustomerCreatedEvent(DomainEvent):
    """Event published when a customer is created."""
    
    def __init__(
        self,
        customer_id: str,
        customer_type: str,
        billing_type: str,
        email: str
    ):
        data = {
            "customer_id": customer_id,
            "customer_type": customer_type,
            "billing_type": billing_type,
            "email": email
        }
        
        super().__init__(
            event_type="customer.created",
            source="neocloud.customers",
            data=data,
            aggregate_id=customer_id
        )


class CustomerUpdatedEvent(DomainEvent):
    """Event published when a customer is updated."""
    
    def __init__(
        self,
        customer_id: str,
        updated_fields: List[str]
    ):
        data = {
            "customer_id": customer_id,
            "updated_fields": updated_fields
        }
        
        super().__init__(
            event_type="customer.updated",
            source="neocloud.customers",
            data=data,
            aggregate_id=customer_id
        )


class CustomerDeletedEvent(DomainEvent):
    """Event published when a customer is deleted."""
    
    def __init__(
        self,
        customer_id: str,
        email: str
    ):
        data = {
            "customer_id": customer_id,
            "email": email
        }
        
        super().__init__(
            event_type="customer.deleted",
            source="neocloud.customers",
            data=data,
            aggregate_id=customer_id
        )


class CustomerStatusChangedEvent(DomainEvent):
    """Event published when a customer status changes."""
    
    def __init__(
        self,
        customer_id: str,
        old_status: str,
        new_status: str
    ):
        data = {
            "customer_id": customer_id,
            "old_status": old_status,
            "new_status": new_status
        }
        
        super().__init__(
            event_type="customer.status_changed",
            source="neocloud.customers",
            data=data,
            aggregate_id=customer_id
        )


class CustomerVerifiedEvent(DomainEvent):
    """Event published when a customer verification status changes."""
    
    def __init__(
        self,
        customer_id: str,
        verification_type: str,  # email, phone, identity
        verified: bool
    ):
        data = {
            "customer_id": customer_id,
            "verification_type": verification_type,
            "verified": verified
        }
        
        super().__init__(
            event_type="customer.verified",
            source="neocloud.customers",
            data=data,
            aggregate_id=customer_id
        )