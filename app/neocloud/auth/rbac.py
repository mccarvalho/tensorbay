"""RBAC roles and permissions (product plan section 20)."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    EXECUTIVE = "EXECUTIVE"
    SALES_MANAGER = "SALES_MANAGER"
    SALES = "SALES"
    FINANCE = "FINANCE"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"
    OPERATIONS = "OPERATIONS"
    CLOUD_ADMIN = "CLOUD_ADMIN"
    CUSTOMER_ADMIN = "CUSTOMER_ADMIN"
    CUSTOMER_USER = "CUSTOMER_USER"


class Permission(StrEnum):
    CUSTOMER_READ = "customer.read"
    CUSTOMER_WRITE = "customer.write"
    CONTRACT_READ = "contract.read"
    CONTRACT_WRITE = "contract.write"
    INVENTORY_READ = "inventory.read"
    INVENTORY_WRITE = "inventory.write"
    SUPPLIER_READ = "supplier.read"
    SUPPLIER_WRITE = "supplier.write"
    CAPACITY_READ = "capacity.read"
    PRICING_READ = "pricing.read"
    PRICING_WRITE = "pricing.write"
    BILLING_READ = "billing.read"
    BILLING_WRITE = "billing.write"
    ALLOCATION_CREATE = "allocation.create"
    ALLOCATION_RELEASE = "allocation.release"
    PROVISIONING_EXECUTE = "provisioning.execute"
    DOCUMENT_GENERATE = "document.generate"
    USER_ADMIN = "user.admin"
    ECONOMICS_READ = "economics.read"
    ECONOMICS_WRITE = "economics.write"
    COMMISSION_APPROVE = "commission.approve"


_ALL = set(Permission)

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SUPER_ADMIN: set(_ALL),
    Role.EXECUTIVE: {
        Permission.CUSTOMER_READ,
        Permission.CONTRACT_READ,
        Permission.INVENTORY_READ,
        Permission.CAPACITY_READ,
        Permission.PRICING_READ,
        Permission.BILLING_READ,
        Permission.SUPPLIER_READ,
        Permission.ECONOMICS_READ,
        Permission.ECONOMICS_WRITE,
    },
    Role.SALES_MANAGER: {
        Permission.CUSTOMER_READ,
        Permission.CUSTOMER_WRITE,
        Permission.CONTRACT_READ,
        Permission.CONTRACT_WRITE,
        Permission.CAPACITY_READ,
        Permission.PRICING_READ,
        Permission.PRICING_WRITE,
        Permission.DOCUMENT_GENERATE,
        Permission.ECONOMICS_READ,
        Permission.ECONOMICS_WRITE,
    },
    Role.SALES: {
        Permission.CUSTOMER_READ,
        Permission.CUSTOMER_WRITE,
        Permission.CONTRACT_READ,
        Permission.CAPACITY_READ,
        Permission.PRICING_READ,
        Permission.DOCUMENT_GENERATE,
        Permission.ECONOMICS_READ,
    },
    Role.FINANCE: {
        Permission.CUSTOMER_READ,
        Permission.CONTRACT_READ,
        Permission.BILLING_READ,
        Permission.BILLING_WRITE,
        Permission.PRICING_READ,
        Permission.ECONOMICS_READ,
        Permission.ECONOMICS_WRITE,
    },
    Role.OPERATIONS_MANAGER: {
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,
        Permission.CAPACITY_READ,
        Permission.ALLOCATION_CREATE,
        Permission.ALLOCATION_RELEASE,
        Permission.PROVISIONING_EXECUTE,
        Permission.SUPPLIER_READ,
        Permission.SUPPLIER_WRITE,
    },
    Role.OPERATIONS: {
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,
        Permission.CAPACITY_READ,
        Permission.SUPPLIER_READ,
        Permission.SUPPLIER_WRITE,
    },
    Role.CLOUD_ADMIN: {
        Permission.INVENTORY_READ,
        Permission.CAPACITY_READ,
        Permission.ALLOCATION_CREATE,
        Permission.ALLOCATION_RELEASE,
        Permission.PROVISIONING_EXECUTE,
    },
    Role.CUSTOMER_ADMIN: {
        Permission.CONTRACT_READ,
        Permission.BILLING_READ,
    },
    Role.CUSTOMER_USER: set(),
}


def permissions_for_roles(roles: list[str]) -> set[Permission]:
    perms: set[Permission] = set()
    for r in roles:
        try:
            perms |= ROLE_PERMISSIONS.get(Role(r), set())
        except ValueError:
            continue  # unknown group, ignore
    return perms
