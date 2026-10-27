// Shared commercial constants mirrored from the backend enums.

// Main NVIDIA data-center GPU models offered (newest first), incl. VR720.
export const GPU_MODELS = [
  'VR720',
  'GB300',
  'B300',
  'GB200',
  'B200',
  'B100',
  'H200',
  'H100',
  'L40S',
  'A100',
  'A40',
  'V100',
] as const;

// catalog.CommercialModel (plan §8).
export const COMMERCIAL_MODELS = [
  'GPU_HOURLY',
  'GPU_MONTHLY',
  'SERVER_HOURLY',
  'DEDICATED_SERVER',
  'RESERVED',
  'COMMITMENT',
  'PREPAID',
  'SPOT',
  'PRIVATE_CLUSTER',
  'TIERED',
  'ENTERPRISE',
  'REVENUE_SHARE',
] as const;

// catalog.SkuCategory
export const SKU_CATEGORIES = ['GPU', 'SERVER', 'CLUSTER', 'STORAGE', 'NETWORK'] as const;

// catalog.PriceBookScope
export const PRICE_BOOK_SCOPES = [
  'LIST',
  'REGIONAL',
  'CUSTOMER',
  'CONTRACT',
  'PROMO',
  'RESERVED',
  'SPOT',
] as const;

export type CommercialModel = (typeof COMMERCIAL_MODELS)[number];
export type SkuCategory = (typeof SKU_CATEGORIES)[number];
export type PriceBookScope = (typeof PRICE_BOOK_SCOPES)[number];

// suppliers.SupplierTier
export const SUPPLIER_TIERS = ['OEM', 'DISTRIBUTOR', 'CLOUD', 'BROKER'] as const;
// suppliers.SupplierStatus
export const SUPPLIER_STATUSES = ['ACTIVE', 'INACTIVE'] as const;
// capacity.ProcurementStatus (incoming-capacity lifecycle)
export const PROCUREMENT_STATUSES = [
  'NEGOTIATING',
  'ORDERED',
  'IN_TRANSIT',
  'DELIVERED',
  'OPERATIONAL',
] as const;
// Statuses that use estimated (expected_*) dates vs. official (actual_*) dates.
export const ESTIMATE_STATUSES = ['NEGOTIATING', 'ORDERED', 'IN_TRANSIT'] as const;
export const ACTUAL_STATUSES = ['DELIVERED', 'OPERATIONAL'] as const;

export type SupplierTier = (typeof SUPPLIER_TIERS)[number];
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number];
export type ProcurementStatus = (typeof PROCUREMENT_STATUSES)[number];

// Gross-profit policy (fractions of selling price).
// TARGET is the margin we aim for on every deal; FLOOR is the hard minimum
// below which a deal must not close. Mirrors the commission plan's
// default_margin_pct governance (floor = 0.30).
export const MARGIN_TARGET_PCT = 0.40;
export const MARGIN_FLOOR_PCT = 0.30;
