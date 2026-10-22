// Client-side RBAC helper. Mirrors app/neocloud/auth/rbac.py so the UI can
// gate write actions. The server still enforces authoritatively; this only
// hides/disables controls the user can't use.
import { decodeClaims, getSession } from './auth';

export type Permission =
  | 'customer.read'
  | 'customer.write'
  | 'contract.read'
  | 'contract.write'
  | 'inventory.read'
  | 'inventory.write'
  | 'supplier.read'
  | 'supplier.write'
  | 'capacity.read'
  | 'pricing.read'
  | 'pricing.write'
  | 'billing.read'
  | 'billing.write'
  | 'allocation.create'
  | 'allocation.release'
  | 'provisioning.execute'
  | 'document.generate'
  | 'user.admin'
  | 'economics.read'
  | 'economics.write'
  | 'commission.approve';

const ALL: Permission[] = [
  'customer.read', 'customer.write', 'contract.read', 'contract.write',
  'inventory.read', 'inventory.write', 'capacity.read', 'pricing.read',
  'pricing.write', 'billing.read', 'billing.write', 'allocation.create',
  'allocation.release', 'provisioning.execute', 'document.generate', 'user.admin',
  'supplier.read', 'supplier.write',
  'economics.read', 'economics.write', 'commission.approve',
];

const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  SUPER_ADMIN: ALL,
  EXECUTIVE: ['customer.read', 'contract.read', 'inventory.read', 'capacity.read', 'pricing.read', 'billing.read', 'supplier.read', 'economics.read', 'economics.write'],
  SALES_MANAGER: ['customer.read', 'customer.write', 'contract.read', 'contract.write', 'capacity.read', 'pricing.read', 'pricing.write', 'document.generate', 'economics.read', 'economics.write'],
  SALES: ['customer.read', 'customer.write', 'contract.read', 'capacity.read', 'pricing.read', 'document.generate', 'economics.read'],
  FINANCE: ['customer.read', 'contract.read', 'billing.read', 'billing.write', 'pricing.read', 'economics.read', 'economics.write'],
  OPERATIONS_MANAGER: ['inventory.read', 'inventory.write', 'capacity.read', 'allocation.create', 'allocation.release', 'provisioning.execute', 'supplier.read', 'supplier.write'],
  OPERATIONS: ['inventory.read', 'inventory.write', 'capacity.read', 'supplier.read', 'supplier.write'],
  CLOUD_ADMIN: ['inventory.read', 'capacity.read', 'allocation.create', 'allocation.release', 'provisioning.execute'],
  CUSTOMER_ADMIN: ['contract.read', 'billing.read'],
  CUSTOMER_USER: [],
};

/** Permissions granted to the currently signed-in user via their Cognito groups. */
export function currentPermissions(): Set<Permission> {
  const perms = new Set<Permission>();
  const session = getSession();
  if (!session?.idToken) return perms;
  let groups: string[] = [];
  try {
    groups = decodeClaims(session.idToken).groups ?? [];
  } catch {
    return perms;
  }
  for (const g of groups) {
    for (const p of ROLE_PERMISSIONS[g] ?? []) perms.add(p);
  }
  return perms;
}

export function hasPermission(p: Permission): boolean {
  return currentPermissions().has(p);
}
