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
