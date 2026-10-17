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
  | 'capacity.read'
  | 'pricing.read'
  | 'pricing.write'
  | 'billing.read'
  | 'billing.write'
  | 'allocation.create'
  | 'allocation.release'
  | 'provisioning.execute'
  | 'document.generate'
  | 'user.admin';

const ALL: Permission[] = [
  'customer.read', 'customer.write', 'contract.read', 'contract.write',
  'inventory.read', 'inventory.write', 'capacity.read', 'pricing.read',
  'pricing.write', 'billing.read', 'billing.write', 'allocation.create',
  'allocation.release', 'provisioning.execute', 'document.generate', 'user.admin',
];

const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  SUPER_ADMIN: ALL,
  EXECUTIVE: ['customer.read', 'contract.read', 'inventory.read', 'capacity.read', 'pricing.read', 'billing.read'],
  SALES_MANAGER: ['customer.read', 'customer.write', 'contract.read', 'contract.write', 'capacity.read', 'pricing.read', 'pricing.write', 'document.generate'],
  SALES: ['customer.read', 'customer.write', 'contract.read', 'capacity.read', 'pricing.read', 'document.generate'],
  FINANCE: ['customer.read', 'contract.read', 'billing.read', 'billing.write', 'pricing.read'],
  OPERATIONS_MANAGER: ['inventory.read', 'inventory.write', 'capacity.read', 'allocation.create', 'allocation.release', 'provisioning.execute'],
  OPERATIONS: ['inventory.read', 'inventory.write', 'capacity.read'],
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
