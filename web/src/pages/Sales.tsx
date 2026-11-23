// Sales Pipeline — EPIC D / plan §9.
// Funnel: Opportunity -> Capacity Check -> Quote (with line items).
import { useMemo, useState, useEffect, useRef, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { useToast, errMessage } from '../components/toast';
import { decodeClaims, getSession } from '../auth';
import { GPU_MODELS, COMMERCIAL_MODELS } from '../constants';
import { hasPermission } from '../permissions';
import PipelineBoard, { type InventoryLane } from './PipelineBoard';
import {
  ACTIVE_STAGES, ESCROW_STAGES, MACRO_STAGES, STAGE_LABEL, STAGE_HINT, STAGE_PROBABILITY, STAGE_TONE,
  isOpenStage, macroOf, type MacroStage, type SalesStage,
} from '../salesStages';
import {
  KpiCard,
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  SearchInput,
  type BadgeTone,
  type Column,
} from '../components/ui';

// --------------------------------------------------------------------------- //
// Types (mirror the backend contract)
// --------------------------------------------------------------------------- //

type QuoteStatus = 'DRAFT' | 'SENT' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED';

type AvailabilityStatus = 'AVAILABLE' | 'PARTIALLY_AVAILABLE' | 'UNAVAILABLE';


/** Signed-in user's identity, for pre-filling the account-owner field. */
function currentUserOwner(): { name: string | null; email: string | null; sub: string | null } {
  const session = getSession();
  if (!session?.idToken) return { name: null, email: null, sub: null };
  try {
    const claims = decodeClaims(session.idToken);
    return {
      name: claims.name ?? claims.email ?? null,
      email: claims.email ?? null,
      sub: claims.sub ?? null,
    };
  } catch {
    return { name: null, email: null, sub: null };
  }
}

const QUOTE_STATUSES: QuoteStatus[] = ['DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED'];

interface Opportunity {
  id: string;
  customer_id: string;
  short_name: string | null;
  created_at: string;
  gpu_model: string;
  sku_id: string | null;
  quantity: number;
  expected_start: string | null;
  duration_months: number;
  commercial_model: string;
  expected_mrr: string | number;
  probability: number;
  sales_stage: SalesStage;
  account_owner: string | null;
  account_owner_email: string | null;
  account_owner_sub: string | null;
  region: string | null;
  assigned_to: string | null;
  next_action: string | null;
  escrow_required: boolean;
}

interface OpportunityInput {
  customer_id: string;
  short_name: string;
  gpu_model: string;
  quantity: number;
  expected_start: string | null;
  duration_months: number;
  commercial_model: string;
  expected_mrr: number;
  probability: number;
  sales_stage: SalesStage;
  account_owner: string | null;
  account_owner_email: string | null;
  account_owner_sub: string | null;
  region: string;
  assigned_to: string;
  next_action: string;
  escrow_required: boolean;
}

interface QuoteItem {
  id?: string;
  sku_id: string;
  quantity: number;
  unit_price: number;
  discount_pct: number;
}

interface Quote {
  id: string;
  opportunity_id: string;
  quote_number: string;
  status: QuoteStatus;
  term_months: number;
  commitment: string | number | null;
  sla: string | null;
  valid_until: string | null;
  total_amount: string | number;
  items: QuoteItem[];
}

interface CustomerLite {
  id: string;
  legal_name: string;
}

interface Sku {
  id: string;
  code: string;
  name: string;
  category: string;
  gpu_model: string | null;
  active: boolean;
}

interface CapacityCheck {
  gpu_model: string;
  requested: number;
  available: number;
  gap: number;
  incoming: number;
  status: AvailabilityStatus;
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

const QUOTE_TONE: Record<QuoteStatus, BadgeTone> = {
  DRAFT: 'neutral',
  SENT: 'cyan',
  ACCEPTED: 'success',
  REJECTED: 'flamingo',
  EXPIRED: 'warning',
};

const AVAIL_TONE: Record<AvailabilityStatus, BadgeTone> = {
  AVAILABLE: 'success',
  PARTIALLY_AVAILABLE: 'warning',
  UNAVAILABLE: 'flamingo',
};

const money = (v: string | number | null | undefined): string => {
  const n = typeof v === 'string' ? Number(v) : (v ?? 0);
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};
const num = (v: number): string => v.toLocaleString('en-US');
const today = (): string => new Date().toISOString().slice(0, 10);

/** Mirrors drive.service.opportunity_folder_name: YYYY-MM-<short name> (creation month). */
function driveFolder(createdAt: string | undefined, shortName: string, gpuModel: string, qty: number): string {
  const d = createdAt ? new Date(createdAt) : new Date();
  const label = shortName.trim() || `${gpuModel}-${qty}`;
  const ym = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
  return `${ym}-${label.replace(/\s*[\\/]+\s*/g, ' - ').replace(/\s+/g, ' ')}`;
}

/** Default win probability for a stage; ON_HOLD has none (a hold keeps the current one). */
const stageProb = (s: SalesStage, current = 0): number => (s === 'ON_HOLD' ? current : STAGE_PROBABILITY[s]);

function emptyOpportunity(stage: SalesStage = 'NEW_LEAD'): OpportunityInput {
  return {
    customer_id: '',
    short_name: '',
    gpu_model: 'H200',
    quantity: 8,
    expected_start: today(),
    duration_months: 12,
    commercial_model: 'GPU_MONTHLY',
    expected_mrr: 0,
    probability: stageProb(stage),
    sales_stage: stage,
    account_owner: currentUserOwner().name,
    account_owner_email: currentUserOwner().email,
    account_owner_sub: currentUserOwner().sub,
    region: '',
    assigned_to: '',
    next_action: '',
    escrow_required: true,
  };
}

function lineTotal(it: QuoteItem): number {
  return it.quantity * it.unit_price * (1 - it.discount_pct / 100);
}

// --------------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------------- //
export default function Sales() {
  const qc = useQueryClient();
  const toast = useToast();
  const [oppModalOpen, setOppModalOpen] = useState(false);
  const [editing, setEditing] = useState<Opportunity | null>(null);
  const [form, setForm] = useState<OpportunityInput>(emptyOpportunity);
  const [quotesFor, setQuotesFor] = useState<Opportunity | null>(null);
  const [search, setSearch] = useState('');
  const canWrite = hasPermission('customer.write');
  // Board (Kanban) is the default; the choice is remembered per browser.
  type View = 'board' | 'inventory' | 'table';
  const [view, setViewState] = useState<View>(() => {
    const v = localStorage.getItem('neocloud.pipeline.view');
    return v === 'table' || v === 'inventory' ? v : 'board';
  });
  const setView = (v: View) => { localStorage.setItem('neocloud.pipeline.view', v); setViewState(v); };
  const [macroFilter, setMacroFilter] = useState<MacroStage['key'] | 'ON_HOLD' | 'LOST' | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);

  const oppsQuery = useQuery({
    queryKey: ['opportunities'],
    queryFn: () => api.get<Opportunity[]>('/v1/sales/opportunities?limit=200'),
  });

  const lanesQuery = useQuery({
    queryKey: ['inventory-lanes'],
    queryFn: () => api.get<InventoryLane[]>('/v1/sales/inventory-lanes'),
    enabled: view === 'inventory',
  });

  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
  });

  const customerName = (id: string): string =>
    customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;

  const createMut = useMutation({
    mutationFn: (payload: OpportunityInput) =>
      api.post<Opportunity>('/v1/sales/opportunities', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      toast.success('Opportunity created');
      closeOppModal();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not create opportunity')),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<OpportunityInput> }) =>
      api.patch<Opportunity>(`/v1/sales/opportunities/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      toast.success('Opportunity updated');
      closeOppModal();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not update opportunity')),
  });

  function openCreate(stage: SalesStage = 'NEW_LEAD') {
    setEditing(null);
    setForm(emptyOpportunity(stage));
    setOppModalOpen(true);
  }

  // Moving a card changes only its stage. The board updates immediately and rolls
  // back if the server refuses, so a drag never leaves the screen out of sync.
  const moveMut = useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: SalesStage }) =>
      api.patch<Opportunity>(`/v1/sales/opportunities/${id}`, { sales_stage: stage }),
    onMutate: async ({ id, stage }) => {
      setMovingId(id);
      await qc.cancelQueries({ queryKey: ['opportunities'] });
      const previous = qc.getQueryData<Opportunity[]>(['opportunities']);
      qc.setQueryData<Opportunity[]>(['opportunities'], (old) =>
        (old ?? []).map((o) => (o.id === id ? { ...o, sales_stage: stage } : o)),
      );
      return { previous };
    },
    onError: (e, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(['opportunities'], ctx.previous);
      toast.error(errMessage(e, 'Could not move the deal'));
    },
    onSuccess: (_d, { stage }) => toast.success(`Moved to ${STAGE_LABEL[stage]}`),
    onSettled: () => {
      setMovingId(null);
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['inventory-lanes'] });
    },
  });

  function moveDeal(o: Opportunity, stage: SalesStage) {
    const who = customerName(o.customer_id);
    if (o.escrow_required === false && ESCROW_STAGES.includes(stage)) {
      toast.error(`${who} has no escrow account, so the Payment substages do not apply. Edit the deal to turn escrow on.`);
      return;
    }
    if (stage === 'WON' && !confirm(`Mark the ${who} deal as WON (live and billing)? It then counts for commissions.`)) return;
    if (stage === 'LOST' && !confirm(`Mark the ${who} deal as LOST?`)) return;
    if (ACTIVE_STAGES.includes(o.sales_stage) && !ACTIVE_STAGES.includes(stage) && !confirm(`${who} is an active contract. Move it to ${STAGE_LABEL[stage]}?`)) return;
    moveMut.mutate({ id: o.id, stage });
  }

  function openEdit(o: Opportunity) {
    setEditing(o);
    setForm({
      customer_id: o.customer_id,
      short_name: o.short_name ?? '',
      gpu_model: o.gpu_model,
      quantity: o.quantity,
      expected_start: o.expected_start,
      duration_months: o.duration_months,
      commercial_model: o.commercial_model,
      expected_mrr: Number(o.expected_mrr),
      probability: o.probability,
      sales_stage: o.sales_stage,
      account_owner: o.account_owner,
      account_owner_email: o.account_owner_email,
      account_owner_sub: o.account_owner_sub,
      region: o.region ?? '',
      assigned_to: o.assigned_to ?? '',
      next_action: o.next_action ?? '',
      escrow_required: o.escrow_required ?? true,
    });
    setOppModalOpen(true);
  }

  function closeOppModal() {
    setOppModalOpen(false);
    setEditing(null);
    setForm(emptyOpportunity());
  }

  function submitOpp(e: FormEvent) {
    e.preventDefault();
    // An empty short name is stored as "none" (the folder then uses <model>-<qty>).
    const blank = (v: string) => (v.trim() || null) as unknown as string;
    const payload = { ...form, short_name: blank(form.short_name), region: blank(form.region), assigned_to: blank(form.assigned_to), next_action: blank(form.next_action) };
    if (editing) updateMut.mutate({ id: editing.id, payload });
    else createMut.mutate(payload);
  }

  // Client-side search over the opportunities list.
  const filteredOpps = useMemo(() => {
    const q = search.trim().toLowerCase();
    const opps = (oppsQuery.data ?? []).filter((o) => {
      if (!macroFilter) return true;
      if (macroFilter === 'ON_HOLD' || macroFilter === 'LOST') return o.sales_stage === macroFilter;
      return macroOf(o.sales_stage)?.key === macroFilter;
    });
    if (!q) return opps;
    return opps.filter((o) =>
      `${o.gpu_model} ${customerName(o.customer_id)} ${o.short_name ?? ''} ${o.region ?? ''} ${STAGE_LABEL[o.sales_stage] ?? o.sales_stage} ${o.commercial_model} ${o.account_owner ?? ''} ${o.assigned_to ?? ''}`
        .toLowerCase().includes(q),
    );
  }, [oppsQuery.data, search, macroFilter, customersQuery.data]);

  // Pipeline KPIs (exclude LOST from weighted/open pipeline)
  const kpis = useMemo(() => {
    const opps = oppsQuery.data ?? [];
    const open = opps.filter((o) => isOpenStage(o.sales_stage));
    const won = opps.filter((o) => ACTIVE_STAGES.includes(o.sales_stage));
    const sumMrr = (list: Opportunity[]) => list.reduce((s, o) => s + Number(o.expected_mrr), 0);
    const weighted = open.reduce((s, o) => s + Number(o.expected_mrr) * (o.probability / 100), 0);
    const gpuDemand = open.reduce((s, o) => s + o.quantity, 0);
    return {
      openCount: open.length,
      openMrr: sumMrr(open),
      weighted,
      wonMrr: sumMrr(won),
      gpuDemand,
    };
  }, [oppsQuery.data]);

  // Counts for the filter chips: five macro stages, then On Hold and Lost.
  const macroCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: 0, ON_HOLD: 0, LOST: 0 };
    for (const m of MACRO_STAGES) counts[m.key] = 0;
    for (const o of oppsQuery.data ?? []) {
      counts.ALL += 1;
      const key = o.sales_stage === 'ON_HOLD' || o.sales_stage === 'LOST' ? o.sales_stage : macroOf(o.sales_stage)?.key;
      if (key) counts[key] += 1;
    }
    return counts;
  }, [oppsQuery.data]);

  const columns: Array<Column<Opportunity>> = [
    { key: 'customer_id', header: 'Customer', render: (o) => customerName(o.customer_id) },
    { key: 'gpu_model', header: 'Model', render: (o) => <Badge tone="grape">{o.gpu_model}</Badge> },
    { key: 'quantity', header: 'Qty', render: (o) => <span className="font-semibold text-white">{num(o.quantity)}</span> },
    { key: 'commercial_model', header: 'Model', render: (o) => <span className="text-xs text-grape-soft">{o.commercial_model}</span> },
    { key: 'duration_months', header: 'Term', render: (o) => `${o.duration_months} mo` },
    { key: 'expected_mrr', header: 'Expected MRR', render: (o) => <span className="font-semibold text-cyan">{money(o.expected_mrr)}</span> },
    { key: 'probability', header: 'Prob.', render: (o) => `${o.probability}%` },
    { key: 'sales_stage', header: 'Stage', render: (o) => <Badge tone={STAGE_TONE[o.sales_stage] ?? 'neutral'}>{STAGE_LABEL[o.sales_stage] ?? o.sales_stage}</Badge> },
    {
      key: 'account_owner',
      header: 'Owner',
      render: (o) =>
        o.account_owner ? (
          <div className="flex flex-col">
            <span className="text-sm text-white">{o.account_owner}</span>
            {o.account_owner_email && (
              <span className="text-xs text-grape-soft">
                {o.account_owner_sub ? '✓ ' : ''}{o.account_owner_email}
              </span>
            )}
          </div>
        ) : (
          <span className="text-grape-soft">—</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (o) => (
        <div className="flex justify-end gap-2">
          <Link to={`/opportunities/${o.id}`} className="btn-ghost px-2.5 py-1 text-xs">View</Link>
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setQuotesFor(o)}>
            Quotes
          </button>
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(o)}>
            Edit
          </button>
        </div>
      ),
      className: 'text-right',
    },
  ];

  const isServerModel = form.commercial_model.includes('SERVER');

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeader
          eyebrow="COMMERCIAL · PIPELINE"
          title="Sales Pipeline"
          description="Opportunities through the funnel — check capacity before quoting, then build priced quotes with line items."
        />
        <div className="flex items-center gap-3">
          <div className="inline-flex overflow-hidden rounded-xl border border-white/10" role="group" aria-label="Pipeline view">
            {(['board', 'inventory', 'table'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 text-sm ${view === v ? 'bg-white/10 text-white' : 'text-grape-soft hover:text-white'}`}
              >
                {v === 'board' ? 'Pipeline (Stage)' : v === 'inventory' ? 'Inventory (GPU)' : 'Table'}
              </button>
            ))}
          </div>
          <button type="button" className="btn-primary" onClick={() => openCreate()}>
            + New Opportunity
          </button>
        </div>
      </div>

      {/* Pipeline KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KpiCard label="Open Opportunities" value={num(kpis.openCount)} accent="white" />
        <KpiCard label="Open Pipeline MRR" value={money(kpis.openMrr)} accent="cyan" />
        <KpiCard label="Weighted MRR" value={money(kpis.weighted)} accent="grape" sub="by probability" />
        <KpiCard label="Active Contract MRR" value={money(kpis.wonMrr)} accent="white" />
        <KpiCard label="Pipeline GPU Demand" value={num(kpis.gpuDemand)} accent="flamingo" sub="open opps" />
      </div>

      {/* Stage filter: five macro stages, then On Hold and Lost */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by stage">
        {([
          { key: null, label: 'All Opportunities', tone: 'neutral' as const, count: macroCounts.ALL },
          ...MACRO_STAGES.map((m) => ({ key: m.key, label: m.label, tone: m.tone, count: macroCounts[m.key] })),
          { key: 'ON_HOLD' as const, label: 'On Hold', tone: 'neutral' as const, count: macroCounts.ON_HOLD },
          { key: 'LOST' as const, label: 'Lost', tone: 'flamingo' as const, count: macroCounts.LOST },
        ]).map((c) => (
          <button
            key={c.key ?? 'ALL'}
            type="button"
            data-testid={`filter-${c.key ?? 'ALL'}`}
            aria-pressed={macroFilter === c.key}
            onClick={() => setMacroFilter(macroFilter === c.key ? null : c.key)}
            className={`flex items-center gap-2 rounded-full border px-1.5 py-1 ${macroFilter === c.key ? 'border-cyan' : 'border-transparent'}`}
          >
            <Badge tone={c.tone}>{c.label}</Badge>
            <span className="pr-1 text-sm text-grape-soft">{c.count}</span>
          </button>
        ))}
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by model, customer, stage, owner…" />

      {oppsQuery.isLoading ? (
        <Spinner label="Loading pipeline…" />
      ) : oppsQuery.isError ? (
        <ErrorState error={oppsQuery.error} />
      ) : view !== 'table' ? (
        <PipelineBoard
          mode={view === 'inventory' ? 'inventory' : 'stage'}
          lanes={lanesQuery.data ?? []}
          macroFilter={macroFilter === 'ON_HOLD' || macroFilter === 'LOST' ? null : macroFilter}
          opportunities={filteredOpps}
          customerName={customerName}
          canWrite={canWrite}
          busyId={movingId}
          onMove={(o, stage) => moveDeal(o as Opportunity, stage)}
          onEdit={(o) => openEdit(o as Opportunity)}
          onQuotes={(o) => setQuotesFor(o as Opportunity)}
          onAdd={(stage) => openCreate(stage)}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={filteredOpps}
          rowKey={(o) => o.id}
          empty={<EmptyState title={search ? 'No matches' : 'No opportunities yet'} hint={search ? 'Try a different search.' : 'Create an opportunity to start building your commercial pipeline.'} />}
        />
      )}

      {/* Create / edit opportunity */}
      <Modal open={oppModalOpen} onClose={closeOppModal} title={editing ? 'Edit Opportunity' : 'New Opportunity'}>
        <form className="flex flex-col gap-4" onSubmit={submitOpp}>
          <div>
            <label className="label" htmlFor="opp_customer">Customer</label>
            <select
              id="opp_customer"
              className="input"
              required
              value={form.customer_id}
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            >
              <option value="" disabled>
                {customersQuery.isLoading ? 'Loading…' : 'Select a customer'}
              </option>
              {customersQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.legal_name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label" htmlFor="opp_short">Short name</label>
            <input id="opp_short" className="input" maxLength={60} placeholder="e.g. Foxgaroo GB200"
              value={form.short_name} onChange={(e) => setForm({ ...form, short_name: e.target.value })} />
            <p className="mt-1 text-xs text-grape-soft" data-testid="opp-folder-preview">
              Drive folder: <span className="text-white">{driveFolder(editing?.created_at, form.short_name, form.gpu_model, form.quantity)}</span>
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_model">{isServerModel ? 'Server / GPU Model' : 'GPU Model'}</label>
              <input
                id="opp_model"
                className="input"
                required
                list="gpu-model-options"
                placeholder={isServerModel ? 'SERVER-8X-H200' : 'H200'}
                value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })}
              />
              <datalist id="gpu-model-options">
                {GPU_MODELS.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="label" htmlFor="opp_qty">Quantity ({isServerModel ? 'servers' : 'GPUs'})</label>
              <input
                id="opp_qty" type="number" min={1} className="input" required
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_cm">Commercial Model</label>
              <select
                id="opp_cm" className="input" required
                value={form.commercial_model}
                onChange={(e) => setForm({ ...form, commercial_model: e.target.value })}
              >
                {COMMERCIAL_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="opp_term">Duration (months)</label>
              <input
                id="opp_term" type="number" min={1} className="input" required
                value={form.duration_months}
                onChange={(e) => setForm({ ...form, duration_months: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="opp_mrr">Expected MRR (USD)</label>
              <input
                id="opp_mrr" type="number" min={0} step="0.01" className="input" required
                value={form.expected_mrr}
                onChange={(e) => setForm({ ...form, expected_mrr: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_prob">Probability (%)</label>
              <input
                id="opp_prob" type="number" min={0} max={100} className="input" required
                value={form.probability}
                onChange={(e) => setForm({ ...form, probability: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_stage">Stage</label>
              <select
                id="opp_stage" className="input" required
                value={form.sales_stage}
                onChange={(e) => {
                  // Picking a stage also proposes its default probability (still editable).
                  const st = e.target.value as SalesStage;
                  setForm({ ...form, sales_stage: st, probability: stageProb(st, form.probability) });
                }}
              >
                {MACRO_STAGES.map((m) => (
                  <optgroup key={m.key} label={`${m.n}. ${m.label}`}>
                    {m.stages.map((s) => (
                      <option key={s} value={s} title={STAGE_HINT[s]} disabled={!form.escrow_required && ESCROW_STAGES.includes(s)}>{STAGE_LABEL[s]}</option>
                    ))}
                  </optgroup>
                ))}
                <option value="ON_HOLD" title={STAGE_HINT.ON_HOLD}>On Hold</option>
                <option value="LOST" title={STAGE_HINT.LOST}>Lost</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_start">Expected Start</label>
              <input
                id="opp_start" type="date" className="input"
                value={form.expected_start ?? ''}
                onChange={(e) => setForm({ ...form, expected_start: e.target.value || null })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_owner">Account Owner</label>
              <OwnerAutocomplete
                value={form.account_owner ?? ''}
                email={form.account_owner_email}
                onChange={(name, email, sub) =>
                  setForm({
                    ...form,
                    account_owner: name || null,
                    account_owner_email: email,
                    account_owner_sub: sub,
                  })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_region">Region</label>
              <input
                id="opp_region" className="input" maxLength={64} placeholder="Brazil (São Paulo)"
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_assigned">Assigned to (person)</label>
              <input
                id="opp_assigned" className="input" maxLength={255} placeholder="Who is responsible now"
                value={form.assigned_to}
                onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="opp_next">Next action</label>
            <input
              id="opp_next" className="input" maxLength={255} placeholder="Review MSA & Order Form"
              value={form.next_action}
              onChange={(e) => setForm({ ...form, next_action: e.target.value })}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-white">
            <input
              type="checkbox" id="opp_escrow"
              checked={form.escrow_required}
              onChange={(e) => setForm({ ...form, escrow_required: e.target.checked })}
            />
            This deal uses an escrow account (turn off to skip the Payment substages)
          </label>

          {/* Capacity check gate */}
          <CapacityCheckPanel gpuModel={form.gpu_model} quantity={form.quantity} />

          {(createMut.isError || updateMut.isError) && (
            <ErrorState error={createMut.error ?? updateMut.error} />
          )}

          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={closeOppModal}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              {createMut.isPending || updateMut.isPending
                ? 'Saving…'
                : editing ? 'Save Changes' : 'Create Opportunity'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Quotes drawer */}
      {quotesFor && (
        <QuotesModal
          opportunity={quotesFor}
          customerName={customerName(quotesFor.customer_id)}
          onClose={() => setQuotesFor(null)}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Capacity Check panel — the gate before quoting (plan §9)
// --------------------------------------------------------------------------- //
function CapacityCheckPanel({ gpuModel, quantity }: { gpuModel: string; quantity: number }) {
  const [checkKey, setCheckKey] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ['capacity-check', checkKey],
    queryFn: () =>
      api.get<CapacityCheck>(
        `/v1/capacity/check?gpu_model=${encodeURIComponent(gpuModel)}&quantity=${quantity}`,
      ),
    enabled: checkKey !== null,
  });

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="eyebrow">Capacity Check</span>
          <p className="text-xs text-grape-soft">Verify availability before quoting.</p>
        </div>
        <button
          type="button"
          className="btn-ghost text-sm"
          disabled={!gpuModel || quantity < 1}
          onClick={() => setCheckKey(`${gpuModel}:${quantity}:${Date.now()}`)}
        >
          Check {num(quantity)} × {gpuModel || '—'}
        </button>
      </div>

      {q.isFetching ? (
        <Spinner label="Checking capacity…" />
      ) : q.isError ? (
        <ErrorState error={q.error} />
      ) : q.data ? (
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <Badge tone={AVAIL_TONE[q.data.status]}>{q.data.status.replace('_', ' ')}</Badge>
          <span className="text-grape-soft">Requested <b className="text-white">{num(q.data.requested)}</b></span>
          <span className="text-grape-soft">Available <b className="text-white">{num(q.data.available)}</b></span>
          <span className="text-grape-soft">Incoming <b className="text-white">{num(q.data.incoming)}</b></span>
          {q.data.gap > 0 && <span className="text-flamingo">Gap <b>{num(q.data.gap)}</b></span>}
        </div>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Quotes modal — list + create quote with line items (SKU picker)
// --------------------------------------------------------------------------- //
function QuotesModal({
  opportunity,
  customerName,
  onClose,
}: {
  opportunity: Opportunity;
  customerName: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const quotesQuery = useQuery({
    queryKey: ['quotes', opportunity.id],
    queryFn: () => api.get<Quote[]>(`/v1/sales/quotes?opportunity_id=${opportunity.id}&limit=200`),
  });

  const skusQuery = useQuery({
    queryKey: ['skus'],
    queryFn: () => api.get<Sku[]>('/v1/catalog/skus?limit=200'),
    enabled: creating,
  });

  const [quoteNumber, setQuoteNumber] = useState(`Q-${Date.now().toString().slice(-6)}`);
  const [status, setStatus] = useState<QuoteStatus>('DRAFT');
  const [termMonths, setTermMonths] = useState(opportunity.duration_months);
  const [validUntil, setValidUntil] = useState<string>('');
  const [sla, setSla] = useState('');
  const [items, setItems] = useState<QuoteItem[]>([
    { sku_id: '', quantity: opportunity.quantity, unit_price: 0, discount_pct: 0 },
  ]);

  const total = useMemo(() => items.reduce((s, it) => s + lineTotal(it), 0), [items]);

  const createMut = useMutation({
    mutationFn: () =>
      api.post<Quote>('/v1/sales/quotes', {
        opportunity_id: opportunity.id,
        quote_number: quoteNumber,
        status,
        term_months: termMonths,
        sla: sla || null,
        valid_until: validUntil || null,
        total_amount: total,
        items: items.filter((it) => it.sku_id),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quotes', opportunity.id] });
      setCreating(false);
    },
  });

  function updateItem(idx: number, patch: Partial<QuoteItem>) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }
  function addItem() {
    setItems((prev) => [...prev, { sku_id: '', quantity: 1, unit_price: 0, discount_pct: 0 }]);
  }
  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  return (
    <Modal open onClose={onClose} title={`Quotes · ${customerName}`}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-grape-soft">
            {opportunity.gpu_model} · {num(opportunity.quantity)} units · {opportunity.commercial_model}
          </p>
          {!creating && (
            <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => setCreating(true)}>
              + New Quote
            </button>
          )}
        </div>

        {!creating ? (
          quotesQuery.isLoading ? (
            <Spinner label="Loading quotes…" />
          ) : quotesQuery.isError ? (
            <ErrorState error={quotesQuery.error} />
          ) : (quotesQuery.data ?? []).length === 0 ? (
            <EmptyState title="No quotes yet" hint="Create a priced quote with line items for this opportunity." />
          ) : (
            <div className="flex flex-col gap-2">
              {quotesQuery.data!.map((qt) => (
                <div key={qt.id} className="card flex items-center justify-between gap-3 py-3">
                  <div>
                    <div className="font-semibold text-white">{qt.quote_number}</div>
                    <div className="text-xs text-grape-soft">
                      {qt.term_months} mo · {qt.items.length} line{qt.items.length === 1 ? '' : 's'}
                      {qt.valid_until ? ` · valid to ${qt.valid_until}` : ''}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-cyan">{money(qt.total_amount)}</span>
                    <Badge tone={QUOTE_TONE[qt.status]}>{qt.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="q_num">Quote Number</label>
                <input id="q_num" className="input" required value={quoteNumber}
                  onChange={(e) => setQuoteNumber(e.target.value)} />
              </div>
              <div>
                <label className="label" htmlFor="q_status">Status</label>
                <select id="q_status" className="input" value={status}
                  onChange={(e) => setStatus(e.target.value as QuoteStatus)}>
                  {QUOTE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label className="label" htmlFor="q_term">Term (months)</label>
                <input id="q_term" type="number" min={1} className="input" required value={termMonths}
                  onChange={(e) => setTermMonths(Number(e.target.value))} />
              </div>
              <div>
                <label className="label" htmlFor="q_valid">Valid Until</label>
                <input id="q_valid" type="date" className="input" value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)} />
              </div>
              <div>
                <label className="label" htmlFor="q_sla">SLA</label>
                <input id="q_sla" className="input" placeholder="99.9%" value={sla}
                  onChange={(e) => setSla(e.target.value)} />
              </div>
            </div>

            {/* Line items */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="label">Line Items</span>
                <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={addItem}>+ Add line</button>
              </div>
              {items.map((it, idx) => (
                <div key={idx} className="grid grid-cols-12 items-end gap-2">
                  <div className="col-span-5">
                    <select className="input" required value={it.sku_id}
                      onChange={(e) => updateItem(idx, { sku_id: e.target.value })}>
                      <option value="" disabled>{skusQuery.isLoading ? 'Loading SKUs…' : 'Select SKU'}</option>
                      {skusQuery.data?.filter((s) => s.active).map((s) => (
                        <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-2">
                    <input type="number" min={1} className="input" placeholder="Qty" value={it.quantity}
                      onChange={(e) => updateItem(idx, { quantity: Number(e.target.value) })} />
                  </div>
                  <div className="col-span-2">
                    <input type="number" min={0} step="0.01" className="input" placeholder="Unit $" value={it.unit_price}
                      onChange={(e) => updateItem(idx, { unit_price: Number(e.target.value) })} />
                  </div>
                  <div className="col-span-2">
                    <input type="number" min={0} max={100} className="input" placeholder="Disc %" value={it.discount_pct}
                      onChange={(e) => updateItem(idx, { discount_pct: Number(e.target.value) })} />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    {items.length > 1 && (
                      <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => removeItem(idx)} aria-label="Remove line">✕</button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between border-t border-white/5 pt-3">
              <span className="text-sm text-grape-soft">Total</span>
              <span className="text-lg font-bold text-cyan">{money(total)}</span>
            </div>

            {createMut.isError && <ErrorState error={createMut.error} />}

            <div className="flex justify-end gap-3">
              <button type="button" className="btn-ghost" onClick={() => setCreating(false)}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={createMut.isPending}>
                {createMut.isPending ? 'Creating…' : 'Create Quote'}
              </button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
// OwnerAutocomplete — free-text account-owner field with a real-time directory
// dropdown. Typing keeps the free text as the name (and clears email/sub, since
// it's no longer a verified directory match); picking a suggestion stores the
// full {name, email, sub}. Backed by GET /v1/directory/users?q=.
// --------------------------------------------------------------------------- //
interface DirectoryUser {
  sub: string;
  email: string | null;
  name: string | null;
}

function OwnerAutocomplete({
  value,
  email,
  onChange,
}: {
  value: string;
  email: string | null;
  onChange: (name: string, email: string | null, sub: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [debounced, setDebounced] = useState(value);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounce the typed value before querying the directory.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value.trim()), 200);
    return () => clearTimeout(t);
  }, [value]);

  // Close the dropdown on outside click.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = useQuery({
    queryKey: ['directory', 'users', debounced],
    queryFn: () =>
      api.get<DirectoryUser[]>(
        `/v1/directory/users${debounced ? `?q=${encodeURIComponent(debounced)}` : ''}`,
      ),
    enabled: open,
    staleTime: 60_000,
  });

  const results = q.data ?? [];

  return (
    <div ref={boxRef} className="relative">
      <input
        id="opp_owner"
        className="input"
        placeholder="Type a name — suggestions from your directory"
        autoComplete="off"
        value={value}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          // Free text: keep the typed name, drop the verified email/sub.
          onChange(e.target.value, null, null);
          setOpen(true);
        }}
      />
      {/* Show the verified email when the current value came from a directory pick. */}
      {email && (
        <p className="mt-1 text-xs text-cyan">✓ {email}</p>
      )}
      {open && (
        <div className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-xl border border-white/10 bg-space-700 shadow-card">
          {q.isLoading ? (
            <div className="px-3 py-2 text-xs text-grape-soft">Searching…</div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-xs text-grape-soft">
              No directory match — free text will be saved as-is.
            </div>
          ) : (
            results.map((u) => {
              const display = u.name ?? u.email ?? u.sub;
              return (
                <button
                  key={u.sub}
                  type="button"
                  className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition hover:bg-white/5"
                  onClick={() => {
                    onChange(display, u.email, u.sub);
                    setOpen(false);
                  }}
                >
                  <span className="text-sm text-white">{display}</span>
                  {u.email && u.email !== display && (
                    <span className="text-xs text-grape-soft">{u.email}</span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
