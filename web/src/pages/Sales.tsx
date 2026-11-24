// Sales Pipeline — EPIC D / plan §9.
// Funnel: Opportunity -> Capacity Check -> Quote (with line items).
import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { useToast, errMessage } from '../components/toast';
import OpportunityFormModal, { type Opportunity } from '../components/OpportunityFormModal';
import { hasPermission } from '../permissions';
import PipelineBoard, { type InventoryLane } from './PipelineBoard';
import {
  ACTIVE_STAGES, ESCROW_STAGES, MACRO_STAGES, STAGE_LABEL, STAGE_TONE,
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




const QUOTE_STATUSES: QuoteStatus[] = ['DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED'];


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

/** $197.5M style, for KPI cards where the full figure would not fit. */
const moneyShort = (v: number): ReactNode => (
  <span className="whitespace-nowrap" title={money(v)}>
    {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(v)}
  </span>
);

const money = (v: string | number | null | undefined): string => {
  const n = typeof v === 'string' ? Number(v) : (v ?? 0);
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};
const num = (v: number): string => v.toLocaleString('en-US');

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
  const [newStage, setNewStage] = useState<SalesStage>('NEW_LEAD');
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

  function openCreate(stage: SalesStage = 'NEW_LEAD') {
    setEditing(null);
    setNewStage(stage);
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
    setOppModalOpen(true);
  }

  function closeOppModal() {
    setOppModalOpen(false);
    setEditing(null);
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
        <KpiCard label="Open Pipeline MRR" value={moneyShort(kpis.openMrr)} accent="cyan" />
        <KpiCard label="Weighted MRR" value={moneyShort(kpis.weighted)} accent="grape" sub="by probability" />
        <KpiCard label="Active Contract MRR" value={moneyShort(kpis.wonMrr)} accent="white" />
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


      <OpportunityFormModal
        open={oppModalOpen}
        onClose={closeOppModal}
        editing={editing}
        stage={newStage}
      />

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

