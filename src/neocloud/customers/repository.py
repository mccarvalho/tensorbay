"""
Customer domain repository for data access.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..common.errors import ResourceNotFoundException
from .models import Customer, CustomerContact, CustomerPaymentMethod
from .schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerContactCreate,
    CustomerContactUpdate,
    CustomerPaymentMethodCreate,
    CustomerPaymentMethodUpdate,
)


class CustomerRepository:
    """Repository for customer data access."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, customer_data: CustomerCreate) -> Customer:
        """Create a new customer."""
        customer = Customer(**customer_data.dict())
        self.session.add(customer)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer
    
    async def get_by_id(self, customer_id: uuid.UUID) -> Optional[Customer]:
        """Get customer by ID with relationships."""
        query = (
            select(Customer)
            .options(
                selectinload(Customer.contacts),
                selectinload(Customer.payment_methods)
            )
            .where(Customer.id == customer_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[Customer]:
        """Get customer by email."""
        query = select(Customer).where(Customer.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update(self, customer_id: uuid.UUID, update_data: CustomerUpdate) -> Customer:
        """Update customer."""
        customer = await self.get_by_id(customer_id)
        if not customer:
            raise ResourceNotFoundException(f"Customer not found: {customer_id}")
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(customer, field, value)
        
        await self.session.flush()
        await self.session.refresh(customer)
        return customer
    
    async def delete(self, customer_id: uuid.UUID) -> bool:
        """Delete customer."""
        customer = await self.get_by_id(customer_id)
        if not customer:
            return False
        
        await self.session.delete(customer)
        return True
    
    async def list_customers(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        customer_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Customer]:
        """List customers with filters."""
        query = select(Customer)
        
        # Apply filters
        if status:
            query = query.where(Customer.status == status)
        if customer_type:
            query = query.where(Customer.customer_type == customer_type)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Customer.name.ilike(search_term)) |
                (Customer.email.ilike(search_term)) |
                (Customer.company_name.ilike(search_term))
            )
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()


class CustomerContactRepository:
    """Repository for customer contact data access."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        customer_id: uuid.UUID,
        contact_data: CustomerContactCreate
    ) -> CustomerContact:
        """Create a new customer contact."""
        # If this is a primary contact, unset existing primary
        if contact_data.is_primary:
            await self._unset_primary_contact(customer_id)
        
        contact = CustomerContact(
            customer_id=customer_id,
            **contact_data.dict()
        )
        self.session.add(contact)
        await self.session.flush()
        await self.session.refresh(contact)
        return contact
    
    async def get_by_id(self, contact_id: uuid.UUID) -> Optional[CustomerContact]:
        """Get contact by ID."""
        query = select(CustomerContact).where(CustomerContact.id == contact_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update(
        self,
        contact_id: uuid.UUID,
        update_data: CustomerContactUpdate
    ) -> CustomerContact:
        """Update customer contact."""
        contact = await self.get_by_id(contact_id)
        if not contact:
            raise ResourceNotFoundException(f"Customer contact not found: {contact_id}")
        
        # If setting as primary, unset existing primary
        if update_data.is_primary:
            await self._unset_primary_contact(contact.customer_id)
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(contact, field, value)
        
        await self.session.flush()
        await self.session.refresh(contact)
        return contact
    
    async def delete(self, contact_id: uuid.UUID) -> bool:
        """Delete customer contact."""
        contact = await self.get_by_id(contact_id)
        if not contact:
            return False
        
        await self.session.delete(contact)
        return True
    
    async def list_by_customer(self, customer_id: uuid.UUID) -> List[CustomerContact]:
        """List contacts for a customer."""
        query = (
            select(CustomerContact)
            .where(CustomerContact.customer_id == customer_id)
            .order_by(CustomerContact.is_primary.desc(), CustomerContact.name)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def _unset_primary_contact(self, customer_id: uuid.UUID) -> None:
        """Unset existing primary contact for customer."""
        query = (
            select(CustomerContact)
            .where(
                CustomerContact.customer_id == customer_id,
                CustomerContact.is_primary == True
            )
        )
        result = await self.session.execute(query)
        existing_primary = result.scalar_one_or_none()
        
        if existing_primary:
            existing_primary.is_primary = False


class CustomerPaymentMethodRepository:
    """Repository for customer payment method data access."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        customer_id: uuid.UUID,
        payment_data: CustomerPaymentMethodCreate
    ) -> CustomerPaymentMethod:
        """Create a new customer payment method."""
        # If this is a default payment method, unset existing default
        if payment_data.is_default:
            await self._unset_default_payment_method(customer_id)
        
        payment_method = CustomerPaymentMethod(
            customer_id=customer_id,
            **payment_data.dict()
        )
        self.session.add(payment_method)
        await self.session.flush()
        await self.session.refresh(payment_method)
        return payment_method
    
    async def get_by_id(self, payment_id: uuid.UUID) -> Optional[CustomerPaymentMethod]:
        """Get payment method by ID."""
        query = select(CustomerPaymentMethod).where(CustomerPaymentMethod.id == payment_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update(
        self,
        payment_id: uuid.UUID,
        update_data: CustomerPaymentMethodUpdate
    ) -> CustomerPaymentMethod:
        """Update customer payment method."""
        payment_method = await self.get_by_id(payment_id)
        if not payment_method:
            raise ResourceNotFoundException(f"Payment method not found: {payment_id}")
        
        # If setting as default, unset existing default
        if update_data.is_default:
            await self._unset_default_payment_method(payment_method.customer_id)
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(payment_method, field, value)
        
        await self.session.flush()
        await self.session.refresh(payment_method)
        return payment_method
    
    async def delete(self, payment_id: uuid.UUID) -> bool:
        """Delete customer payment method."""
        payment_method = await self.get_by_id(payment_id)
        if not payment_method:
            return False
        
        await self.session.delete(payment_method)
        return True
    
    async def list_by_customer(self, customer_id: uuid.UUID) -> List[CustomerPaymentMethod]:
        """List payment methods for a customer."""
        query = (
            select(CustomerPaymentMethod)
            .where(CustomerPaymentMethod.customer_id == customer_id)
            .order_by(CustomerPaymentMethod.is_default.desc(), CustomerPaymentMethod.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def _unset_default_payment_method(self, customer_id: uuid.UUID) -> None:
        """Unset existing default payment method for customer."""
        query = (
            select(CustomerPaymentMethod)
            .where(
                CustomerPaymentMethod.customer_id == customer_id,
                CustomerPaymentMethod.is_default == True
            )
        )
        result = await self.session.execute(query)
        existing_default = result.scalar_one_or_none()
        
        if existing_default:
            existing_default.is_default = False