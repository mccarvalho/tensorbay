// Deal phases, in funnel order — mirrors SalesStage in
// app/neocloud/domains/sales/models.py (codes, order and default probabilities
// must stay in sync; the backend is the source of truth for probabilities and
// sets them itself when a deal changes stage).
import type { BadgeTone } from './components/ui';

export type SalesStage =
  | 'PROSPECTING'
  | 'QUALIFICATION'
  | 'PROPOSAL'
  | 'POC'
  | 'NEGOTIATION' // shown as "Contract review" (code kept for existing deals)
  | 'SIGNED'
  | 'DELIVERY'
  | 'ACCEPTANCE'
  | 'WON'
  | 'LOST';

export const SALES_STAGES: SalesStage[] = [
  'PROSPECTING', 'QUALIFICATION', 'PROPOSAL', 'POC', 'NEGOTIATION',
  'SIGNED', 'DELIVERY', 'ACCEPTANCE', 'WON', 'LOST',
];

export const STAGE_LABEL: Record<SalesStage, string> = {
  PROSPECTING: 'Prospecting',
  QUALIFICATION: 'Qualification',
  PROPOSAL: 'Proposal',
  POC: 'PoC',
  NEGOTIATION: 'Contract review',
  SIGNED: 'Signed · KYC & Escrow',
  DELIVERY: 'Delivery',
  ACCEPTANCE: 'Acceptance',
  WON: 'Won',
  LOST: 'Lost',
};

export const STAGE_HINT: Record<SalesStage, string> = {
  PROSPECTING: 'First contact',
  QUALIFICATION: 'Need and budget confirmed',
  PROPOSAL: 'Offer sent, with a validity date',
  POC: 'Paid proof of concept (up to 7 days)',
  NEGOTIATION: 'MSA, Order Form and escrow agreement under review',
  SIGNED: 'Order Form signed; KYC and escrow deposit within 5 business days',
  DELIVERY: 'Cluster being delivered; deployment clock running',
  ACCEPTANCE: '5-day acceptance; prepayment still in escrow',
  WON: 'Accepted; escrow released. Counts for commissions',
  LOST: 'Lost',
};

export const STAGE_TONE: Record<SalesStage, BadgeTone> = {
  PROSPECTING: 'neutral',
  QUALIFICATION: 'cyan',
  PROPOSAL: 'grape',
  POC: 'cyan',
  NEGOTIATION: 'warning',
  SIGNED: 'grape',
  DELIVERY: 'warning',
  ACCEPTANCE: 'cyan',
  WON: 'success',
  LOST: 'flamingo',
};

export const STAGE_PROBABILITY: Record<SalesStage, number> = {
  PROSPECTING: 10, QUALIFICATION: 20, PROPOSAL: 35, POC: 50, NEGOTIATION: 60,
  SIGNED: 80, DELIVERY: 90, ACCEPTANCE: 95, WON: 100, LOST: 0,
};

/** Display name for any stage code, including ones this build doesn't know. */
export const stageLabel = (s: string): string =>
  STAGE_LABEL[s as SalesStage] ?? s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ');
