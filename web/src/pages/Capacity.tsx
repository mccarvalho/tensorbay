// Capacity — per-model ledger lookup, a capacity-check panel, and the
// incoming-capacity pipeline. Both ledger and check require a gpu_model, so a
// model input drives the view.
import { useState, useMemo, type FormEvent } from 'react';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { GPU_MODELS } from '../constants';
import {
  SectionHeader,
  KpiCard,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  type BadgeTone,
  type Column,
} from '../components/ui';

interface Ledger {
  gpu_model: string;
  physical: number;
  offline: number;
  maintenance: number;
  operational: number;
  reserved: number;
  allocated: number;
  available: number;
}

type CheckStatus = 'AVAILABLE' | 'PARTIALLY_AVAILABLE' | 'UNAVAILABLE';

interface CapacityCheck {
  gpu_model: string;
  requested: number;
  available: number;
  gap: number;
  incoming: number;
  status: CheckStatus;
}

interface IncomingCapacity {
  id: string;
  gpu_model: string;
  quantity: number;
  expected_delivery: string | null;
  expected_operational: string | null;
  purchase_order: string | null;
  notes: string | null;
}

const CHECK_TONE: Record<CheckStatus, BadgeTone> = {
  AVAILABLE: 'success',
  PARTIALLY_AVAILABLE: 'warning',
  UNAVAILABLE: 'flamingo',
};

export default function Capacity() {
  const [model, setModel] = useState('');
  const [submittedModel, setSubmittedModel] = useState('');
  const [quantity, setQuantity] = useState(8);
  const [checkArgs, setCheckArgs] = useState<{ model: string; quantity: number } | null>(null);

  const ledgerQuery = useQuery({
    queryKey: ['capacity', 'ledger', submittedModel],
    queryFn: () => api.get<Ledger>(`/v1/capacity/ledger?gpu_model=${encodeURIComponent(submittedModel)}`),
    enabled: submittedModel.length > 0,
  });

  const checkQuery = useQuery({
    queryKey: ['capacity', 'check', checkArgs],
    queryFn: () =>
      api.get<CapacityCheck>(
        `/v1/capacity/check?gpu_model=${encodeURIComponent(checkArgs!.model)}&quantity=${checkArgs!.quantity}`,
      ),
    enabled: checkArgs !== null,
  });

  return (
    <div className="flex flex-col gap-10">
      <SectionHeader
        eyebrow="CAPACITY · GPU LEDGER"
        title="Capacity Planning"
        description="Look up the live capacity ledger per GPU model, run availability checks, and review incoming supply."
      />

      {/* Fleet-wide capacity + overselling overview + incoming timeline */}
      <FleetOverview />

      {/* Ledger lookup */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">LEDGER · BY MODEL</span>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmittedModel(model.trim());
          }}
        >
          <div className="min-w-[220px] flex-1">
            <label className="label" htmlFor="ledger_model">GPU Model</label>
            <input
              id="ledger_model"
              className="input"
              list="capacity-gpu-models"
              placeholder="e.g. H100"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={model.trim().length === 0}>
            Look up
          </button>
        </form>

        {submittedModel.length === 0 ? (
          <EmptyState title="Enter a GPU model" hint="Type a model above to pull its live capacity ledger." />
        ) : ledgerQuery.isLoading ? (
          <Spinner label="Loading ledger…" />
        ) : ledgerQuery.isError ? (
          <ErrorState error={ledgerQuery.error} />
        ) : ledgerQuery.data ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-7">
            <KpiCard label="Physical" value={ledgerQuery.data.physical.toLocaleString('en-US')} accent="white" />
            <KpiCard label="Operational" value={ledgerQuery.data.operational.toLocaleString('en-US')} accent="cyan" />
            <KpiCard label="Available" value={ledgerQuery.data.available.toLocaleString('en-US')} accent="cyan" />
            <KpiCard label="Reserved" value={ledgerQuery.data.reserved.toLocaleString('en-US')} accent="grape" />
            <KpiCard label="Allocated" value={ledgerQuery.data.allocated.toLocaleString('en-US')} accent="grape" />
            <KpiCard label="Maintenance" value={ledgerQuery.data.maintenance.toLocaleString('en-US')} accent="white" />
            <KpiCard label="Offline" value={ledgerQuery.data.offline.toLocaleString('en-US')} accent="flamingo" />
          </div>
        ) : null}
      </section>

      {/* Capacity check */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">CHECK · AVAILABILITY</span>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (model.trim().length > 0) setCheckArgs({ model: model.trim(), quantity });
          }}
        >
          <div className="min-w-[200px] flex-1">
            <label className="label" htmlFor="check_model">GPU Model</label>
            <input
              id="check_model"
              className="input"
              list="capacity-gpu-models"
              placeholder="e.g. H100"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>
          <div className="w-32">
            <label className="label" htmlFor="check_qty">Quantity</label>
            <input
              id="check_qty"
              type="number"
              min={1}
              className="input"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={model.trim().length === 0}>
            Check
          </button>
        </form>

        {checkArgs === null ? (
          <EmptyState title="Run a capacity check" hint="Enter a model and quantity to see if the fleet can satisfy demand." />
        ) : checkQuery.isLoading ? (
          <Spinner label="Checking availability…" />
        ) : checkQuery.isError ? (
          <ErrorState error={checkQuery.error} />
        ) : checkQuery.data ? (
          <div className="card-glow flex flex-wrap items-center gap-8">
            <div className="flex flex-col gap-1">
              <span className="label">Status</span>
              <Badge tone={CHECK_TONE[checkQuery.data.status]}>{checkQuery.data.status}</Badge>
            </div>
            <div className="flex flex-col">
              <span className="label">Requested</span>
              <span className="text-2xl font-bold text-white">{checkQuery.data.requested}</span>
            </div>
            <div className="flex flex-col">
              <span className="label">Available</span>
              <span className="text-2xl font-bold text-cyan">{checkQuery.data.available}</span>
            </div>
            <div className="flex flex-col">
              <span className="label">Gap</span>
              <span className="text-2xl font-bold text-flamingo">{checkQuery.data.gap}</span>
            </div>
            <div className="flex flex-col">
              <span className="label">Incoming</span>
              <span className="text-2xl font-bold text-grape">{checkQuery.data.incoming}</span>
            </div>
          </div>
        ) : null}
      </section>

      {/* Incoming capacity */}
      <IncomingSection />

      <datalist id="capacity-gpu-models">
        {GPU_MODELS.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Incoming capacity — full CRUD (writes gated by inventory.write)
// --------------------------------------------------------------------------- //
interface IncomingForm {
  gpu_model: string;
  quantity: number;
  expected_delivery: string;
  expected_operational: string;
  purchase_order: string;
  notes: string;
}
const emptyIncoming = (): IncomingForm => ({
  gpu_model: 'H200', quantity: 8, expected_delivery: '', expected_operational: '', purchase_order: '', notes: '',
});

function IncomingSection() {
  const qc = useQueryClient();
  const canWrite = hasPermission('inventory.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<IncomingForm>(emptyIncoming);
  const reset = () => { setEditId(null); setForm(emptyIncoming()); };

  const incomingQuery = useQuery({
    queryKey: ['capacity', 'incoming'],
    queryFn: () => api.get<IncomingCapacity[]>('/v1/capacity/incoming?limit=200'),
  });

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        gpu_model: form.gpu_model,
        quantity: Number(form.quantity),
        expected_delivery: form.expected_delivery || null,
        expected_operational: form.expected_operational || null,
        purchase_order: form.purchase_order || null,
        notes: form.notes || null,
      };
      return editId
        ? api.patch<IncomingCapacity>(`/v1/capacity/incoming/${editId}`, payload)
        : api.post<IncomingCapacity>('/v1/capacity/incoming', payload);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['capacity', 'incoming'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/capacity/incoming/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['capacity', 'incoming'] }),
  });

  function openEdit(r: IncomingCapacity) {
    setEditId(r.id);
    setForm({
      gpu_model: r.gpu_model, quantity: r.quantity,
      expected_delivery: r.expected_delivery ?? '', expected_operational: r.expected_operational ?? '',
      purchase_order: r.purchase_order ?? '', notes: r.notes ?? '',
    });
    setOpen(true);
  }

  const cols: Array<Column<IncomingCapacity>> = [
    { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
    { key: 'quantity', header: 'Quantity', render: (r) => r.quantity.toLocaleString('en-US') },
    { key: 'expected_delivery', header: 'Expected Delivery', render: (r) => r.expected_delivery ?? '—' },
    { key: 'expected_operational', header: 'Expected Operational', render: (r) => r.expected_operational ?? '—' },
    { key: 'purchase_order', header: 'PO', render: (r) => r.purchase_order ?? '—' },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: IncomingCapacity) => (
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(r)}>Edit</button>
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
          onClick={() => { if (confirm(`Delete incoming ${r.quantity}× ${r.gpu_model}?`)) del.mutate(r.id); }}>Delete</button>
      </div>) } as Column<IncomingCapacity>] : []),
  ];

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow">SUPPLY · INCOMING</span>
        {canWrite && <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => { reset(); setOpen(true); }}>+ New Incoming</button>}
      </div>
      {del.isError && <ErrorState error={del.error} />}
      {incomingQuery.isLoading ? (
        <Spinner label="Loading incoming supply…" />
      ) : incomingQuery.isError ? (
        <ErrorState error={incomingQuery.error} />
      ) : (
        <DataTable columns={cols} rows={incomingQuery.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No incoming capacity" hint="Record purchase orders / planned hardware to feed capacity planning." />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Incoming Capacity' : 'New Incoming Capacity'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="inc_model">GPU Model</label>
              <input id="inc_model" className="input" required list="capacity-gpu-models" value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="inc_qty">Quantity</label>
              <input id="inc_qty" type="number" min={0} className="input" required value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="inc_del">Expected Delivery</label>
              <input id="inc_del" type="date" className="input" value={form.expected_delivery}
                onChange={(e) => setForm({ ...form, expected_delivery: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="inc_op">Expected Operational</label>
              <input id="inc_op" type="date" className="input" value={form.expected_operational}
                onChange={(e) => setForm({ ...form, expected_operational: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="inc_po">Purchase Order</label>
            <input id="inc_po" className="input" placeholder="PO-2026-0042" value={form.purchase_order}
              onChange={(e) => setForm({ ...form, purchase_order: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="inc_notes">Notes</label>
            <textarea id="inc_notes" className="input" rows={2} value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          {save.isError && <ErrorState error={save.error} />}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Incoming'}
            </button>
          </div>
        </form>
      </Modal>
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Fleet-wide capacity overview (plan §12): per-model stacked ledger bars with
// an overselling indicator, plus an incoming-supply timeline. Dependency-free
// (CSS bars) — charts lib lands with the Executive Dashboard.
// --------------------------------------------------------------------------- //
interface GpuAsset { id: string; model: string }

// Segment colors map to the brand palette.
const SEG: Array<{ key: keyof Ledger; label: string; cls: string }> = [
  { key: 'available', label: 'Available', cls: 'bg-cyan' },
  { key: 'reserved', label: 'Reserved', cls: 'bg-grape' },
  { key: 'allocated', label: 'Allocated', cls: 'bg-flamingo' },
  { key: 'maintenance', label: 'Maintenance', cls: 'bg-grape-soft/60' },
  { key: 'offline', label: 'Offline', cls: 'bg-white/15' },
];

function FleetOverview() {
  // Pull the deployed GPU assets to discover which models actually exist.
  const gpus = useQuery({
    queryKey: ['capacity', 'fleet', 'gpus'],
    queryFn: () => api.get<GpuAsset[]>('/v1/inventory/gpus?limit=500'),
  });

  const models = useMemo(() => {
    const set = new Set<string>();
    for (const g of gpus.data ?? []) if (g.model) set.add(g.model);
    // Order by the canonical GPU_MODELS list, unknowns last (alpha).
    const order = new Map<string, number>(GPU_MODELS.map((m, i) => [m, i]));
    return [...set].sort((a, b) => (order.get(a) ?? 999) - (order.get(b) ?? 999) || a.localeCompare(b));
  }, [gpus.data]);

  // One ledger query per model, in parallel.
  const ledgers = useQueries({
    queries: models.map((m) => ({
      queryKey: ['capacity', 'ledger', m],
      queryFn: () => api.get<Ledger>(`/v1/capacity/ledger?gpu_model=${encodeURIComponent(m)}`),
      enabled: models.length > 0,
    })),
  });

  // Incoming grouped by expected-operational month for the timeline.
  const incoming = useQuery({
    queryKey: ['capacity', 'incoming'],
    queryFn: () => api.get<IncomingCapacity[]>('/v1/capacity/incoming?limit=200'),
  });

  const timeline = useMemo(() => {
    const byMonth = new Map<string, { total: number; byModel: Map<string, number> }>();
    for (const r of incoming.data ?? []) {
      const d = r.expected_operational ?? r.expected_delivery;
      const month = d ? d.slice(0, 7) : 'Unscheduled';
      const bucket = byMonth.get(month) ?? { total: 0, byModel: new Map() };
      bucket.total += r.quantity;
      bucket.byModel.set(r.gpu_model, (bucket.byModel.get(r.gpu_model) ?? 0) + r.quantity);
      byMonth.set(month, bucket);
    }
    return [...byMonth.entries()].sort((a, b) => {
      if (a[0] === 'Unscheduled') return 1;
      if (b[0] === 'Unscheduled') return -1;
      return a[0].localeCompare(b[0]);
    });
  }, [incoming.data]);

  const loading = gpus.isLoading || ledgers.some((l) => l.isLoading && l.fetchStatus !== 'idle');

  return (
    <section className="flex flex-col gap-6">
      <span className="eyebrow">FLEET · CAPACITY &amp; OVERSELLING</span>

      {gpus.isError ? (
        <ErrorState error={gpus.error} />
      ) : loading ? (
        <Spinner label="Building fleet overview…" />
      ) : models.length === 0 ? (
        <EmptyState title="No GPUs deployed yet" hint="Register GPU assets in Inventory to populate the fleet capacity view." />
      ) : (
        <div className="card flex flex-col gap-5">
          {/* Legend */}
          <div className="flex flex-wrap gap-4 text-xs text-grape-soft">
            {SEG.map((s) => (
              <span key={s.key} className="flex items-center gap-1.5">
                <span className={`inline-block h-2.5 w-2.5 rounded-sm ${s.cls}`} />
                {s.label}
              </span>
            ))}
          </div>

          {/* One stacked bar per model */}
          <div className="flex flex-col gap-4">
            {models.map((m, i) => {
              const data = ledgers[i]?.data;
              if (!data) return null;
              const total = data.physical || 1;
              const committed = data.reserved + data.allocated;
              // Overselling = commitments exceed operational capacity.
              const oversold = committed > data.operational;
              return (
                <div key={m} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge tone="grape">{m}</Badge>
                      <span className="text-grape-soft">{data.physical.toLocaleString('en-US')} physical</span>
                      {oversold && <Badge tone="flamingo">OVERSOLD</Badge>}
                    </div>
                    <span className="text-xs text-grape-soft">
                      {data.available.toLocaleString('en-US')} available · {committed.toLocaleString('en-US')} committed
                    </span>
                  </div>
                  <div className="flex h-5 w-full overflow-hidden rounded-md bg-white/5" role="img"
                    aria-label={`${m}: ${data.available} available, ${data.reserved} reserved, ${data.allocated} allocated of ${data.physical} physical`}>
                    {SEG.map((s) => {
                      const v = data[s.key] as number;
                      if (!v) return null;
                      return <div key={s.key} className={s.cls} style={{ width: `${(v / total) * 100}%` }} title={`${s.label}: ${v}`} />;
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Incoming supply timeline */}
      <div className="flex flex-col gap-3">
        <span className="eyebrow">INCOMING · TIMELINE</span>
        {incoming.isLoading ? (
          <Spinner label="Loading incoming timeline…" />
        ) : incoming.isError ? (
          <ErrorState error={incoming.error} />
        ) : timeline.length === 0 ? (
          <EmptyState title="No scheduled supply" hint="Add incoming capacity below to see hardware arriving over time." />
        ) : (
          <div className="card flex flex-col gap-3">
            {(() => {
              const max = Math.max(...timeline.map(([, b]) => b.total), 1);
              return timeline.map(([month, bucket]) => (
                <div key={month} className="flex items-center gap-3">
                  <span className="w-24 shrink-0 text-xs font-medium text-grape-soft">
                    {month === 'Unscheduled' ? month : formatMonth(month)}
                  </span>
                  <div className="flex-1">
                    <div className="h-6 rounded-md bg-brand-gradient" style={{ width: `${(bucket.total / max) * 100}%`, minWidth: '2.5rem' }}
                      title={[...bucket.byModel.entries()].map(([mdl, q]) => `${q}× ${mdl}`).join(', ')} />
                  </div>
                  <span className="w-28 shrink-0 text-right text-sm font-semibold text-white">
                    +{bucket.total.toLocaleString('en-US')} GPUs
                  </span>
                </div>
              ));
            })()}
          </div>
        )}
      </div>
    </section>
  );
}

function formatMonth(ym: string): string {
  const [y, m] = ym.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}
