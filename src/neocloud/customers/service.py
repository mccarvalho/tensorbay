import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.common.errors import NotFoundError
from neocloud.common.events import event_publisher
from neocloud.common.pagination import PaginatedResponse, PaginationParams
from neocloud.customers.models import BillingAccount, Contact, Customer
from neocloud.customers.schemas import (
    BillingAccountCreate,
    ContactCreate,
    CustomerCreate,
    CustomerUpdate,
)


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_customer(self, data: CustomerCreate, created_by: uuid.UUID) -> Customer:
        customer = Customer(**data.model_dump())
        self.db.add(customer)
        await self.db.flush()

        await event_publisher.publish(
            source="customers",
            detail_type="CustomerCreated",
            detail={"customer_id": str(customer.id), "name": customer.legal_name},
        )
        return customer

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError("Customer", str(customer_id))
        return customer

    async def list_customers(
        self,
        pagination: PaginationParams,
        search: str | None = None,
        status_filter: str | None = None,
    ) -> PaginatedResponse:
        query = select(Customer)
        count_query = select(func.count()).select_from(Customer)

        if search:
            query = query.where(Customer.legal_name.ilike(f"%{search}%"))
            count_query = count_query.where(Customer.legal_name.ilike(f"%{search}%"))

        if status_filter:
            query = query.where(Customer.status == status_filter)
            count_query = count_query.where(Customer.status == status_filter)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset(pagination.offset).limit(pagination.page_size).order_by(Customer.created_at.desc())
        )
        items = list(result.scalars().all())

        return PaginatedResponse.create(items=items, total=total, params=pagination)

    async def update_customer(self, customer_id: uuid.UUID, data: CustomerUpdate) -> Customer:
        customer = await self.get_customer(customer_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)
        await self.db.flush()
        return customer

    async def create_contact(self, customer_id: uuid.UUID, data: ContactCreate) -> Contact:
        await self.get_customer(customer_id)  # Verify customer exists
        contact = Contact(customer_id=customer_id, **data.model_dump())
        self.db.add(contact)
        await self.db.flush()
        return contact

    async def list_contacts(self, customer_id: uuid.UUID) -> list[Contact]:
        result = await self.db.execute(select(Contact).where(Contact.customer_id == customer_id))
        return list(result.scalars().all())

    async def create_billing_account(self, customer_id: uuid.UUID, data: BillingAccountCreate) -> BillingAccount:
        await self.get_customer(customer_id)
        account = BillingAccount(customer_id=customer_id, **data.model_dump())
        self.db.add(account)
        await self.db.flush()
        return account

    async def list_billing_accounts(self, customer_id: uuid.UUID) -> list[BillingAccount]:
        result = await self.db.execute(select(BillingAccount).where(BillingAccount.customer_id == customer_id))
        return list(result.scalars().all())
