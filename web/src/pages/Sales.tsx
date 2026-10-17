// Sales Pipeline — EPIC D / plan §9.
// Funnel: Opportunity -> Capacity Check -> Quote (with line items).
import { useMemo, useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { decodeClaims, getSession } from '../auth';
import { GPU_MODELS, COMMERCIAL_MODELS } from '../constants';
import {
  KpiCard,
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  type BadgeTone,
  type Column,
} from '../components/ui';

// --------------------------------------------------------------------------- //
// Types (mirror the backend contract)
// --------------------------------------------------------------------------- //
type SalesStage =
  | 'PROSPECTING'
  | 'QUALIFICATION'
  | 'PROPOSAL'
  | 'NEGOTIATION'
  | 'WON'
  | 'LOST';

type QuoteStatus = 'DRAFT' | 'SENT' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED';

type AvailabilityStatus = 'AVAILABLE' | 'PARTIALLY_AVAILABLE' | 'UNAVAILABLE';

const SALES_STAGES: SalesStage[] = [
  'PROSPECTING',
  'QUALIFICATION',
  'PROPOSAL',
  'NEGOTIATION',
  'WON',
  'LOST',
];

/** Full name (or email) of the signed-in user, for pre-filling owner fields. */
function currentUserName(): string {
  const session = getSession();
  if (!session?.idToken) return '';
  try {
    const claims = decodeClaims(session.idToken);
    return claims.name ?? claims.email ?? '';
  } catch {
    return '';
  }
}

const QUOTE_STATUSES: QuoteStatus[] = ['DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED'];

interface Opportunity {
  id: string;
  customer_id: string;
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
}

interface OpportunityInput {
  customer_id: string;
  gpu_model: string;
  quantity: number;
  expected_start: string | null;
  duration_months: number;
  commercial_model: string;
  expected_mrr: number;
  probability: number;
  sales_stage: SalesStage;
  account_owner: string | null;
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
const STAGE_TONE: Record<SalesStage, BadgeTone> = {
  PROSPECTING: 'neutral',
  QUALIFICATION: 'cyan',
  PROPOSAL: 'grape',
  NEGOTIATION: 'warning',
  WON: 'success',
  LOST: 'flamingo',
};

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

function emptyOpportunity(): OpportunityInput {
  return {
    customer_id: '',
    gpu_model: 'H200',
    quantity: 8,
    expected_start: today(),
    duration_months: 12,
    commercial_model: 'GPU_MONTHLY',
    expected_mrr: 0,
    probability: 50,
    sales_stage: 'PROSPECTING',
    account_owner: currentUserName() || null,
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
  const [oppModalOpen, setOppModalOpen] = useState(false);
  const [editing, setEditing] = useState<Opportunity | null>(null);
  const [form, setForm] = useState<OpportunityInput>(emptyOpportunity);
  const [quotesFor, setQuotesFor] = useState<Opportunity | null>(null);

  const oppsQuery = useQuery({
    queryKey: ['opportunities'],
    queryFn: () => api.get<Opportunity[]>('/v1/sales/opportunities?limit=200'),
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
      closeOppModal();
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<OpportunityInput> }) =>
      api.patch<Opportunity>(`/v1/sales/opportunities/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      closeOppModal();
    },
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyOpportunity());
    setOppModalOpen(true);
  }

  function openEdit(o: Opportunity) {
    setEditing(o);
    setForm({
      customer_id: o.customer_id,
      gpu_model: o.gpu_model,
      quantity: o.quantity,
      expected_start: o.expected_start,
      duration_months: o.duration_months,
      commercial_model: o.commercial_model,
      expected_mrr: Number(o.expected_mrr),
      probability: o.probability,
      sales_stage: o.sales_stage,
      account_owner: o.account_owner,
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
    if (editing) updateMut.mutate({ id: editing.id, payload: form });
    else createMut.mutate(form);
  }

  // Pipeline KPIs (exclude LOST from weighted/open pipeline)
  const kpis = useMemo(() => {
    const opps = oppsQuery.data ?? [];
    const open = opps.filter((o) => o.sales_stage !== 'WON' && o.sales_stage !== 'LOST');
    const won = opps.filter((o) => o.sales_stage === 'WON');
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

  const stageCounts = useMemo(() => {
    const counts: Record<SalesStage, number> = {
      PROSPECTING: 0, QUALIFICATION: 0, PROPOSAL: 0, NEGOTIATION: 0, WON: 0, LOST: 0,
    };
    for (const o of oppsQuery.data ?? []) counts[o.sales_stage] += 1;
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
    { key: 'sales_stage', header: 'Stage', render: (o) => <Badge tone={STAGE_TONE[o.sales_stage]}>{o.sales_stage}</Badge> },
    {
      key: 'actions',
      header: '',
      render: (o) => (
        <div className="flex justify-end gap-2">
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
        <button type="button" className="btn-primary" onClick={openCreate}>
          + New Opportunity
        </button>
      </div>

      {/* Pipeline KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KpiCard label="Open Opportunities" value={num(kpis.openCount)} accent="white" />
        <KpiCard label="Open Pipeline MRR" value={money(kpis.openMrr)} accent="cyan" />
        <KpiCard label="Weighted MRR" value={money(kpis.weighted)} accent="grape" sub="by probability" />
        <KpiCard label="Won MRR" value={money(kpis.wonMrr)} accent="white" />
        <KpiCard label="Pipeline GPU Demand" value={num(kpis.gpuDemand)} accent="flamingo" sub="open opps" />
      </div>

      {/* Stage distribution */}
      <div className="flex flex-wrap gap-2">
        {SALES_STAGES.map((s) => (
          <span key={s} className="flex items-center gap-2">
            <Badge tone={STAGE_TONE[s]}>{s}</Badge>
            <span className="text-sm text-grape-soft">{stageCounts[s]}</span>
          </span>
        ))}
      </div>

      {oppsQuery.isLoading ? (
        <Spinner label="Loading pipeline…" />
      ) : oppsQuery.isError ? (
        <ErrorState error={oppsQuery.error} />
      ) : (
        <DataTable
          columns={columns}
          rows={oppsQuery.data ?? []}
          rowKey={(o) => o.id}
          empty={<EmptyState title="No opportunities yet" hint="Create an opportunity to start building your commercial pipeline." />}
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
                onChange={(e) => setForm({ ...form, sales_stage: e.target.value as SalesStage })}
              >
                {SALES_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
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
              <input
                id="opp_owner" className="input" placeholder="optional"
                value={form.account_owner ?? ''}
                onChange={(e) => setForm({ ...form, account_owner: e.target.value || null })}
              />
            </div>
          </div>

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
