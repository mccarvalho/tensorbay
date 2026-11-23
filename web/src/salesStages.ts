// Deal substages and the five macro stages — mirrors SalesStage / MACRO_STAGES in
// app/neocloud/domains/sales/models.py (codes, order and default probabilities
// must stay in sync; the backend is the source of truth for probabilities and
// sets them itself when a deal changes stage). A deal stores only its substage;
// the macro stage and its owning department are derived here.
import type { BadgeTone } from './components/ui';

export type SalesStage =
  | 'NEW_LEAD' | 'CONTACTED' | 'INTRO_CALL' | 'PROPOSAL_SENT' | 'POC'
  | 'KYC_SCREENING' | 'DOCS_SENT' | 'UNDER_REVIEW' | 'SIGNED'
  | 'ESCROW_SETUP' | 'AWAITING_DEPOSIT' | 'ESCROW_FUNDED'
  | 'PROVISIONING' | 'READY_FOR_TESTING' | 'ACCEPTANCE_TESTING' | 'ACCEPTED'
  | 'WON' | 'SUPPORT_SLA' | 'RENEWAL'
  | 'ON_HOLD' | 'LOST';

export interface MacroStage {
  key: 'LEAD' | 'KYC' | 'PAYMENT' | 'DEPLOYMENT' | 'ACTIVE';
  n: number;
  label: string;
  department: string;
  tone: BadgeTone;
  stages: SalesStage[];
}

export const MACRO_STAGES: MacroStage[] = [
  { key: 'LEAD', n: 1, label: 'Lead', department: 'Commercial · Sales & Partnerships', tone: 'cyan',
    stages: ['NEW_LEAD', 'CONTACTED', 'INTRO_CALL', 'PROPOSAL_SENT', 'POC'] },
  { key: 'KYC', n: 2, label: 'KYC & Contracts', department: 'Legal & Compliance', tone: 'warning',
    stages: ['KYC_SCREENING', 'DOCS_SENT', 'UNDER_REVIEW', 'SIGNED'] },
  { key: 'PAYMENT', n: 3, label: 'Payment', department: 'Finance', tone: 'grape',
    stages: ['ESCROW_SETUP', 'AWAITING_DEPOSIT', 'ESCROW_FUNDED'] },
  { key: 'DEPLOYMENT', n: 4, label: 'Deployment', department: 'Technical Operations', tone: 'grape',
    stages: ['PROVISIONING', 'READY_FOR_TESTING', 'ACCEPTANCE_TESTING', 'ACCEPTED'] },
  { key: 'ACTIVE', n: 5, label: 'Active Contract', department: 'Customer Success', tone: 'success',
    stages: ['WON', 'SUPPORT_SLA', 'RENEWAL'] },
];

/** Every substage in funnel order, then the two outside the flow. */
export const SALES_STAGES: SalesStage[] = [...MACRO_STAGES.flatMap((m) => m.stages), 'ON_HOLD', 'LOST'];

export const ESCROW_STAGES: SalesStage[] = ['ESCROW_SETUP', 'AWAITING_DEPOSIT', 'ESCROW_FUNDED'];
/** Substages of a running contract: these count for commissions and as "won". */
export const ACTIVE_STAGES: SalesStage[] = MACRO_STAGES[4].stages;
/** Not being worked any more (or paused): excluded from the open pipeline. */
export const isOpenStage = (s: string): boolean =>
  !(ACTIVE_STAGES as string[]).includes(s) && s !== 'ON_HOLD' && s !== 'LOST';

export const macroOf = (s: string): MacroStage | undefined => MACRO_STAGES.find((m) => (m.stages as string[]).includes(s));

export const STAGE_LABEL: Record<SalesStage, string> = {
  NEW_LEAD: 'New Lead', CONTACTED: 'Contacted', INTRO_CALL: 'Intro Call', PROPOSAL_SENT: 'Proposal Sent', POC: 'PoC',
  KYC_SCREENING: 'KYC Screening', DOCS_SENT: 'MSA / Order Form Sent', UNDER_REVIEW: 'Under Review', SIGNED: 'Signed',
  ESCROW_SETUP: 'Escrow Setup', AWAITING_DEPOSIT: 'Awaiting Deposit', ESCROW_FUNDED: 'Escrow Funded',
  PROVISIONING: 'Provisioning', READY_FOR_TESTING: 'Ready for Testing', ACCEPTANCE_TESTING: 'Acceptance Testing', ACCEPTED: 'Accepted',
  WON: 'Won · Live / Billing', SUPPORT_SLA: 'Support & SLA', RENEWAL: 'Renewal / Expansion',
  ON_HOLD: 'On Hold', LOST: 'Lost',
};

export const STAGE_HINT: Record<SalesStage, string> = {
  NEW_LEAD: 'Lead just arrived', CONTACTED: 'First contact made', INTRO_CALL: 'Intro call held; need and budget confirmed',
  PROPOSAL_SENT: 'Offer sent, with a validity date', POC: 'Paid proof of concept (up to 7 days)',
  KYC_SCREENING: 'KYC screening of the customer', DOCS_SENT: 'MSA and Order Form sent for signature',
  UNDER_REVIEW: 'Customer and legal reviewing the contract', SIGNED: 'Order Form signed',
  ESCROW_SETUP: 'Escrow account being set up', AWAITING_DEPOSIT: 'Waiting for the escrow deposit (5 business days)',
  ESCROW_FUNDED: 'Prepayment is in escrow',
  PROVISIONING: 'Cluster being provisioned; deployment clock running', READY_FOR_TESTING: 'Ready for the customer to test',
  ACCEPTANCE_TESTING: '5-day acceptance testing', ACCEPTED: 'Customer accepted the cluster',
  WON: 'Contract is live and billing. Counts for commissions', SUPPORT_SLA: 'Running under support and SLA',
  RENEWAL: 'Renewal or expansion in progress',
  ON_HOLD: 'Paused; the previous stage is remembered', LOST: 'Lost',
};

export const STAGE_TONE: Record<SalesStage, BadgeTone> = Object.fromEntries([
  ...MACRO_STAGES.flatMap((m) => m.stages.map((s) => [s, m.tone] as const)),
  ['ON_HOLD', 'neutral'], ['LOST', 'flamingo'],
]) as Record<SalesStage, BadgeTone>;

export const STAGE_PROBABILITY: Record<Exclude<SalesStage, 'ON_HOLD'>, number> = {
  NEW_LEAD: 10, CONTACTED: 15, INTRO_CALL: 20, PROPOSAL_SENT: 35, POC: 50,
  KYC_SCREENING: 55, DOCS_SENT: 60, UNDER_REVIEW: 65, SIGNED: 80,
  ESCROW_SETUP: 82, AWAITING_DEPOSIT: 85, ESCROW_FUNDED: 90,
  PROVISIONING: 90, READY_FOR_TESTING: 92, ACCEPTANCE_TESTING: 94, ACCEPTED: 97,
  WON: 100, SUPPORT_SLA: 100, RENEWAL: 100, LOST: 0,
};

/** Display name for any stage code, including ones this build doesn't know. */
export const stageLabel = (s: string): string =>
  STAGE_LABEL[s as SalesStage] ?? s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ');
