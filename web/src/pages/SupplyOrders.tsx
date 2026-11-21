// Supply orders + supply forecast (Capacity page).
// An order is a GPU purchase contract recorded by totals (e.g. 64 HGX B300
// servers x 8 = 512 GPUs) with its delivery lots. No SKU-by-SKU registration:
// servers/GPUs go into Inventory later, when serial numbers are known.
// The forecast shows GPUs becoming available per model and month, for sales.
import { useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { GPU_MODELS, PROCUREMENT_STATUSES, type ProcurementStatus } from '../constants';
import { useToast, errMessage } from '../components/toast';
import { Badge, DataTable, EmptyState, ErrorState, Modal, Spinner, type BadgeTone, type Column } from '../components/ui';

interface Lot {
  id: string; lot_label: string | null; quantity: number; servers: number | null; status: ProcurementStatus;
  expected_delivery: string | null; expected_operational: string | null;
  actual_delivery: string | null; actual_operational: string | null; notes: string | null;
}
interface SupplyOrder {
  id: string; reference: string; supplier_id: string | null; supplier_quote: string | null;
  status: ProcurementStatus; signed_on: string | null; gpu_model: string; server_model: string | null;
  gpus_per_server: number; servers: number; gpus_total: number;
  unit_price_per_server: string | null; total_value: string | null; currency: string | null;
  payment_terms: string | null; assembly_site: string | null; destination_site: string | null;
  tax_regime: string | null; delivery_window: string | null; notes: string | null;
  scheduled_gpus: number; unscheduled_gpus: number; unallocated_gpus: number;
  delivered_gpus: number; operational_gpus: number; next_delivery: string | null; lots: Lot[];
}
interface Forecast {
  start_month: string; months: number;
  models: Array<{
    gpu_model: string; contracted: number; negotiating: number; delivered: number; operational: number;
    unscheduled: number; overdue: number; months: Array<{ month: string; arriving: number; cumulative: number }>;
  }>;
}
interface SupplierLite { id: string; name: string }

const TONE: Record<ProcurementStatus, BadgeTone> = {
  NEGOTIATING: 'neutral', ORDERED: 'cyan', IN_TRANSIT: 'warning', DELIVERED: 'grape', OPERATIONAL: 'success',
};
const n = (v: number) => v.toLocaleString('en-US');
const money = (v: string | number | null, cur: string | null) =>
  v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: cur || 'USD', maximumFractionDigits: 2 });
const fmtDate = (d: string | null) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { dateStyle: 'medium' }) : '—');
const fmtMonth = (ym: string) => {
  const [y, m] = ym.split('-');
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
};

function useSuppliers() {
  const q = useQuery({ queryKey: ['suppliers', 'lite'], queryFn: () => api.get<SupplierLite[]>('/v1/suppliers?limit=200') });
  const name = useMemo(() => new Map((q.data ?? []).map((s) => [s.id, s.name])), [q.data]);
  return { list: q.data ?? [], name };
}

const refreshKeys = (qc: ReturnType<typeof useQueryClient>) => {
  for (const k of [['capacity', 'orders'], ['capacity', 'forecast'], ['capacity', 'incoming'], ['capacity', 'check']])
    qc.invalidateQueries({ queryKey: k });
};

// --------------------------------------------------------------------------- //
// Forecast
// --------------------------------------------------------------------------- //
export function SupplyForecast() {
  const q = useQuery({ queryKey: ['capacity', 'forecast'], queryFn: () => api.get<Forecast>('/v1/capacity/forecast?months=15') });
  return (
    <section className="flex flex-col gap-3" data-testid="supply-forecast">
      <span className="eyebrow">SUPPLY · FORECAST</span>
      <p className="text-sm text-grape-soft">
        Contracted GPUs becoming available, by month (cumulative). Each lot counts in the month it is expected to be operational,
        or its delivery month if that is all we know.
      </p>
      {q.isLoading ? <Spinner label="Loading forecast…" /> : q.isError ? <ErrorState error={q.error} /> : (q.data?.models.length ?? 0) === 0 ? (
        <EmptyState title="No contracted supply yet" hint="Register a supply order below to see GPUs arriving over time." />
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-grape-soft">
                <th className="sticky left-0 bg-space-900/95 px-4 py-3">Model</th>
                <th className="px-3 py-3 text-right">Contracted</th>
                <th className="px-3 py-3 text-right">Delivered</th>
                <th className="px-3 py-3 text-right">No date yet</th>
                {q.data!.models[0].months.map((m) => <th key={m.month} className="px-3 py-3 text-right">{fmtMonth(m.month)}</th>)}
              </tr>
            </thead>
            <tbody>
              {q.data!.models.map((m) => (
                <tr key={m.gpu_model} className="border-b border-white/5" data-testid={`forecast-${m.gpu_model}`}>
                  <td className="sticky left-0 bg-space-900/95 px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <Badge tone="grape">{m.gpu_model}</Badge>
                      {m.negotiating > 0 && <span className="text-xs text-grape-soft">+{n(m.negotiating)} negotiating</span>}
                      {m.overdue > 0 && <span className="text-xs text-flamingo">{n(m.overdue)} overdue</span>}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right font-semibold text-white">{n(m.contracted)}</td>
                  <td className="px-3 py-3 text-right">{n(m.delivered)}</td>
                  <td className="px-3 py-3 text-right text-grape-soft">{n(m.unscheduled)}</td>
                  {m.months.map((x) => (
                    <td key={x.month} className="px-3 py-3 text-right" title={`${n(x.arriving)} arriving in ${fmtMonth(x.month)}`}>
                      <div className={x.cumulative ? 'font-semibold text-cyan' : 'text-grape-soft/50'}>{x.cumulative ? n(x.cumulative) : '·'}</div>
                      {x.arriving > 0 && <div className="text-xs text-emerald-300">+{n(x.arriving)}</div>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Orders
// --------------------------------------------------------------------------- //
interface LotDraft { label: string; servers: string; expected_delivery: string; expected_operational: string }
const emptyLot = (i: number): LotDraft => ({ label: `Lot ${i}`, servers: '', expected_delivery: '', expected_operational: '' });

interface OrderForm {
  reference: string; supplier_id: string; supplier_quote: string; status: ProcurementStatus; signed_on: string;
  gpu_model: string; server_model: string; gpus_per_server: string; servers: string;
  unit_price_per_server: string; total_value: string; currency: string; payment_terms: string;
  assembly_site: string; destination_site: string; tax_regime: string; delivery_window: string; notes: string;
}
const emptyOrder = (): OrderForm => ({
  reference: '', supplier_id: '', supplier_quote: '', status: 'ORDERED', signed_on: '',
  gpu_model: 'B300', server_model: '', gpus_per_server: '8', servers: '',
  unit_price_per_server: '', total_value: '', currency: 'USD', payment_terms: '',
  assembly_site: '', destination_site: '', tax_regime: '', delivery_window: '', notes: '',
});
const orNull = (v: string) => (v.trim() === '' ? null : v.trim());

export function SupplyOrdersSection() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('inventory.write');
  const suppliers = useSuppliers();
  const orders = useQuery({ queryKey: ['capacity', 'orders'], queryFn: () => api.get<SupplyOrder[]>('/v1/capacity/orders') });
  const [editing, setEditing] = useState<SupplyOrder | 'new' | null>(null);
  const [lotEdit, setLotEdit] = useState<{ order: SupplyOrder; lot: Lot | null } | null>(null);

  const delOrder = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/capacity/orders/${id}`),
    onSuccess: () => { refreshKeys(qc); toast.success('Order deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete order')),
  });

  return (
    <section className="flex flex-col gap-4" data-testid="supply-orders">
      <div className="flex items-center justify-between">
        <span className="eyebrow">SUPPLY · ORDERS</span>
        {canWrite && <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => setEditing('new')}>+ New supply order</button>}
      </div>
      {orders.isLoading ? <Spinner label="Loading supply orders…" /> : orders.isError ? <ErrorState error={orders.error} /> : (orders.data ?? []).length === 0 ? (
        <EmptyState title="No supply orders" hint="Register a GPU purchase by totals (servers × GPUs) and its delivery forecast." />
      ) : (
        <div className="flex flex-col gap-4">
          {orders.data!.map((o) => (
            <OrderCard key={o.id} order={o} supplier={o.supplier_id ? suppliers.name.get(o.supplier_id) ?? '—' : '—'}
              canWrite={canWrite}
              onEdit={() => setEditing(o)}
              onDelete={() => { if (confirm(`Delete order ${o.reference}? Its delivery lots are removed too.`)) delOrder.mutate(o.id); }}
              onLot={(lot) => setLotEdit({ order: o, lot })}
            />
          ))}
        </div>
      )}
      {editing && (
        <OrderModal order={editing === 'new' ? null : editing} suppliers={suppliers.list}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refreshKeys(qc); }} />
      )}
      {lotEdit && (
        <LotModal order={lotEdit.order} lot={lotEdit.lot} onClose={() => setLotEdit(null)}
          onSaved={() => { setLotEdit(null); refreshKeys(qc); }} />
      )}
    </section>
  );
}

function OrderCard({ order: o, supplier, canWrite, onEdit, onDelete, onLot }: {
  order: SupplyOrder; supplier: string; canWrite: boolean; onEdit: () => void; onDelete: () => void; onLot: (lot: Lot | null) => void;
}) {
  const pct = (v: number) => `${(v / Math.max(o.gpus_total, 1)) * 100}%`;
  const scheduledOpen = o.scheduled_gpus - o.delivered_gpus;
  const cols: Array<Column<Lot>> = [
    { key: 'l', header: 'Lot', render: (l) => <span className="font-medium text-white">{l.lot_label ?? '—'}</span> },
    { key: 'q', header: 'Size', render: (l) => <span>{l.servers != null ? `${n(l.servers)} servers · ` : ''}{n(l.quantity)} GPUs</span> },
    { key: 's', header: 'Status', render: (l) => <Badge tone={TONE[l.status]}>{l.status.replace('_', ' ')}</Badge> },
    { key: 'd', header: 'Delivery', render: (l) => l.actual_delivery ? <span className="text-emerald-300">{fmtDate(l.actual_delivery)}</span> : <span>{l.expected_delivery ? `exp. ${fmtDate(l.expected_delivery)}` : <span className="text-grape-soft">no date yet</span>}</span> },
    { key: 'o', header: 'Operational', render: (l) => l.actual_operational ? <span className="text-emerald-300">{fmtDate(l.actual_operational)}</span> : <span>{l.expected_operational ? `exp. ${fmtDate(l.expected_operational)}` : '—'}</span> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (l: Lot) => (
      <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => onLot(l)}>Edit</button>
    ) } as Column<Lot>] : []),
  ];
  return (
    <article className="card flex flex-col gap-4" data-testid={`order-${o.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold text-white">{o.reference}</span>
            <Badge tone={TONE[o.status]}>{o.status.replace('_', ' ')}</Badge>
            <Badge tone="grape">{o.gpu_model}</Badge>
          </div>
          <span className="text-sm text-grape-soft">
            {supplier}{o.server_model ? ` · ${o.server_model}` : ''}{o.supplier_quote ? ` · quote ${o.supplier_quote}` : ''}
          </span>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-cyan">{n(o.gpus_total)} GPUs</div>
          <div className="text-xs text-grape-soft">{n(o.servers)} servers × {o.gpus_per_server} · {money(o.total_value, o.currency)}</div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex h-3 w-full overflow-hidden rounded bg-white/5" role="img"
          aria-label={`${o.operational_gpus} operational, ${o.delivered_gpus} delivered, ${scheduledOpen} scheduled, ${o.unscheduled_gpus + o.unallocated_gpus} without date`}>
          <div className="bg-emerald-400" style={{ width: pct(o.operational_gpus) }} />
          <div className="bg-grape" style={{ width: pct(o.delivered_gpus - o.operational_gpus) }} />
          <div className="bg-cyan/70" style={{ width: pct(scheduledOpen) }} />
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-grape-soft">
          <span><span className="text-emerald-300">■</span> {n(o.operational_gpus)} operational</span>
          <span><span className="text-grape">■</span> {n(o.delivered_gpus - o.operational_gpus)} delivered</span>
          <span><span className="text-cyan">■</span> {n(scheduledOpen)} scheduled</span>
          <span>□ {n(o.unscheduled_gpus + o.unallocated_gpus)} no date yet</span>
          {o.next_delivery && <span className="text-white">Next delivery: {fmtDate(o.next_delivery)}</span>}
        </div>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['Assembly', o.assembly_site], ['Destination', o.destination_site], ['Tax regime', o.tax_regime],
          ['Delivery window', o.delivery_window], ['Payment', o.payment_terms], ['Signed', o.signed_on ? fmtDate(o.signed_on) : null],
          ['Price / server', o.unit_price_per_server ? money(o.unit_price_per_server, o.currency) : null],
        ].filter(([, v]) => v).map(([k, v]) => (
          <div key={k as string}><dt className="text-xs text-grape-soft">{k}</dt><dd className="text-white">{v}</dd></div>
        ))}
      </dl>
      {o.notes && <p className="whitespace-pre-wrap text-sm text-grape-soft">{o.notes}</p>}

      <DataTable columns={cols} rows={o.lots} rowKey={(l) => l.id} empty={<EmptyState title="No lots" hint="Add the first delivery lot." />} />

      {canWrite && (
        <div className="flex flex-wrap justify-end gap-2">
          {o.unallocated_gpus > 0 && <span className="mr-auto self-center text-xs text-amber-300">{n(o.unallocated_gpus)} GPUs not in any lot yet</span>}
          <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={() => onLot(null)} disabled={o.unallocated_gpus === 0}
            title={o.unallocated_gpus === 0 ? 'All GPUs of this order are already in lots — shrink a lot first' : ''}>+ Add lot</button>
          <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={onEdit}>Edit order</button>
          <button type="button" className="btn-ghost px-3 py-1.5 text-sm text-flamingo" onClick={onDelete}>Delete</button>
        </div>
      )}
    </article>
  );
}

function OrderModal({ order, suppliers, onClose, onSaved }: {
  order: SupplyOrder | null; suppliers: SupplierLite[]; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState<OrderForm>(() => order ? {
    reference: order.reference, supplier_id: order.supplier_id ?? '', supplier_quote: order.supplier_quote ?? '',
    status: order.status, signed_on: order.signed_on ?? '', gpu_model: order.gpu_model, server_model: order.server_model ?? '',
    gpus_per_server: String(order.gpus_per_server), servers: String(order.servers),
    unit_price_per_server: order.unit_price_per_server ?? '', total_value: order.total_value ?? '', currency: order.currency ?? 'USD',
    payment_terms: order.payment_terms ?? '', assembly_site: order.assembly_site ?? '', destination_site: order.destination_site ?? '',
    tax_regime: order.tax_regime ?? '', delivery_window: order.delivery_window ?? '', notes: order.notes ?? '',
  } : emptyOrder());
  const [lots, setLots] = useState<LotDraft[]>([emptyLot(1)]);
  const set = (k: keyof OrderForm) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  const gpus = (Number(f.servers) || 0) * (Number(f.gpus_per_server) || 0);
  const computed = f.unit_price_per_server && f.servers ? Number(f.unit_price_per_server) * Number(f.servers) : null;
  const lotServers = lots.reduce((s, l) => s + (Number(l.servers) || 0), 0);
  const restServers = (Number(f.servers) || 0) - lotServers;

  const save = useMutation({
    mutationFn: () => {
      const body = {
        reference: f.reference.trim(), supplier_id: orNull(f.supplier_id), supplier_quote: orNull(f.supplier_quote),
        status: f.status, signed_on: orNull(f.signed_on), gpu_model: f.gpu_model.trim(), server_model: orNull(f.server_model),
        gpus_per_server: Number(f.gpus_per_server), servers: Number(f.servers),
        unit_price_per_server: orNull(f.unit_price_per_server), currency: orNull(f.currency),
        payment_terms: orNull(f.payment_terms), assembly_site: orNull(f.assembly_site), destination_site: orNull(f.destination_site),
        tax_regime: orNull(f.tax_regime), delivery_window: orNull(f.delivery_window), notes: orNull(f.notes),
        ...(f.total_value.trim() ? { total_value: f.total_value.trim() } : {}),
      };
      if (order) return api.patch<SupplyOrder>(`/v1/capacity/orders/${order.id}`, body);
      const filled = lots.filter((l) => Number(l.servers) > 0);
      const lotBody = filled.map((l) => ({
        label: orNull(l.label), servers: Number(l.servers),
        expected_delivery: orNull(l.expected_delivery), expected_operational: orNull(l.expected_operational),
      }));
      // Whatever isn't in a dated lot stays in an unscheduled "remaining" lot.
      if (filled.length && restServers > 0) lotBody.push({ label: 'Remaining (no date yet)', servers: restServers, expected_delivery: null, expected_operational: null });
      return api.post<SupplyOrder>('/v1/capacity/orders', { ...body, lots: lotBody });
    },
    onSuccess: () => { toast.success(order ? 'Order updated' : 'Supply order created'); onSaved(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save the order')),
  });

  return (
    <Modal open onClose={onClose} title={order ? `Edit ${order.reference}` : 'New supply order'}>
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div><label className="label" htmlFor="so_ref">Reference *</label>
            <input id="so_ref" className="input" required maxLength={128} placeholder="Positivo Request 7995995" value={f.reference} onChange={set('reference')} /></div>
          <div><label className="label" htmlFor="so_sup">Supplier</label>
            <select id="so_sup" className="input" value={f.supplier_id} onChange={set('supplier_id')}>
              <option value="">—</option>{suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select></div>
          <div><label className="label" htmlFor="so_model">GPU model *</label>
            <input id="so_model" className="input" required list="so-gpu-models" value={f.gpu_model} onChange={set('gpu_model')} />
            <datalist id="so-gpu-models">{GPU_MODELS.map((m) => <option key={m} value={m} />)}</datalist></div>
          <div><label className="label" htmlFor="so_srv">Server model</label>
            <input id="so_srv" className="input" placeholder="Supermicro SYS-822GS-NB3RT" value={f.server_model} onChange={set('server_model')} /></div>
          <div><label className="label" htmlFor="so_n">Servers *</label>
            <input id="so_n" className="input" type="number" min={1} required value={f.servers} onChange={set('servers')} /></div>
          <div><label className="label" htmlFor="so_gps">GPUs per server *</label>
            <input id="so_gps" className="input" type="number" min={1} required value={f.gpus_per_server} onChange={set('gpus_per_server')} /></div>
        </div>
        <p className="-mt-2 text-sm"><span className="text-grape-soft">Total: </span><span className="font-semibold text-cyan" data-testid="so-total-gpus">{n(gpus)} GPUs</span></p>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label" htmlFor="so_price">Price per server</label>
            <input id="so_price" className="input" type="number" min={0} step="0.01" value={f.unit_price_per_server} onChange={set('unit_price_per_server')} /></div>
          <div><label className="label" htmlFor="so_cur">Currency</label>
            <input id="so_cur" className="input" maxLength={3} value={f.currency} onChange={set('currency')} /></div>
          <div><label className="label" htmlFor="so_total">Contract total</label>
            <input id="so_total" className="input" type="number" min={0} step="0.01" value={f.total_value} onChange={set('total_value')}
              placeholder={computed != null ? `${computed.toFixed(2)} (calculated)` : 'optional'} /></div>
          <div><label className="label" htmlFor="so_status">Status</label>
            <select id="so_status" className="input" value={f.status} onChange={set('status')}>
              {PROCUREMENT_STATUSES.filter((s) => s === 'NEGOTIATING' || s === 'ORDERED').map((s) => <option key={s} value={s}>{s}</option>)}
            </select></div>
          <div><label className="label" htmlFor="so_signed">Signed on</label>
            <input id="so_signed" className="input" type="date" value={f.signed_on} onChange={set('signed_on')} /></div>
          <div><label className="label" htmlFor="so_quote">Supplier quote #</label>
            <input id="so_quote" className="input" value={f.supplier_quote} onChange={set('supplier_quote')} /></div>
          <div><label className="label" htmlFor="so_asm">Assembly site</label>
            <input id="so_asm" className="input" placeholder="Positivo Manaus (PPB)" value={f.assembly_site} onChange={set('assembly_site')} /></div>
          <div><label className="label" htmlFor="so_dst">Destination</label>
            <input id="so_dst" className="input" placeholder="Ascenty SP" value={f.destination_site} onChange={set('destination_site')} /></div>
          <div><label className="label" htmlFor="so_tax">Tax regime</label>
            <input id="so_tax" className="input" placeholder="REDATA" value={f.tax_regime} onChange={set('tax_regime')} /></div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div><label className="label" htmlFor="so_pay">Payment terms</label>
            <input id="so_pay" className="input" placeholder="40% on order / 60% on invoicing" value={f.payment_terms} onChange={set('payment_terms')} /></div>
          <div><label className="label" htmlFor="so_win">Delivery window</label>
            <input id="so_win" className="input" placeholder="6–13 months" value={f.delivery_window} onChange={set('delivery_window')} /></div>
        </div>
        <div><label className="label" htmlFor="so_notes">Notes</label>
          <textarea id="so_notes" className="input" rows={2} value={f.notes} onChange={set('notes')} /></div>

        {!order && (
          <div className="flex flex-col gap-2 rounded-xl border border-white/10 p-3">
            <span className="label">Delivery forecast</span>
            <p className="text-xs text-grape-soft">Add the lots you already know. Servers not in a lot are kept as “no date yet” and can be scheduled later.</p>
            {lots.map((l, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                <input className="input" aria-label={`Lot ${i + 1} name`} value={l.label} onChange={(e) => setLots(lots.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} />
                <input className="input" type="number" min={1} aria-label={`Lot ${i + 1} servers`} placeholder="servers" value={l.servers}
                  onChange={(e) => setLots(lots.map((x, j) => j === i ? { ...x, servers: e.target.value } : x))} />
                <input className="input" type="date" aria-label={`Lot ${i + 1} expected delivery`} title="Expected delivery" value={l.expected_delivery}
                  onChange={(e) => setLots(lots.map((x, j) => j === i ? { ...x, expected_delivery: e.target.value } : x))} />
                <input className="input" type="date" aria-label={`Lot ${i + 1} expected operational`} title="Expected operational (optional)" value={l.expected_operational}
                  onChange={(e) => setLots(lots.map((x, j) => j === i ? { ...x, expected_operational: e.target.value } : x))} />
                <button type="button" className="btn-ghost text-xs" onClick={() => setLots(lots.length > 1 ? lots.filter((_, j) => j !== i) : [emptyLot(1)])}>Remove</button>
              </div>
            ))}
            <div className="flex items-center justify-between text-xs">
              <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => setLots([...lots, emptyLot(lots.length + 1)])}>+ Lot</button>
              <span className={restServers < 0 ? 'text-flamingo' : 'text-grape-soft'}>
                {restServers < 0 ? `${n(-restServers)} servers over the order` : `${n(restServers)} servers without a date`}
              </span>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={save.isPending || (!order && restServers < 0)}>{save.isPending ? 'Saving…' : order ? 'Save' : 'Create order'}</button>
        </div>
      </form>
    </Modal>
  );
}

function LotModal({ order, lot, onClose, onSaved }: { order: SupplyOrder; lot: Lot | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const maxServers = Math.floor((order.unallocated_gpus + (lot?.quantity ?? 0)) / order.gpus_per_server);
  const [f, setF] = useState({
    label: lot?.lot_label ?? `Lot ${order.lots.length + 1}`,
    servers: lot ? String(lot.servers ?? lot.quantity / order.gpus_per_server) : String(maxServers),
    status: lot?.status ?? (order.status === 'NEGOTIATING' ? 'NEGOTIATING' : 'ORDERED') as ProcurementStatus,
    expected_delivery: lot?.expected_delivery ?? '', expected_operational: lot?.expected_operational ?? '',
    actual_delivery: lot?.actual_delivery ?? '', actual_operational: lot?.actual_operational ?? '', notes: lot?.notes ?? '',
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        label: orNull(f.label), servers: Number(f.servers), status: f.status,
        expected_delivery: orNull(f.expected_delivery), expected_operational: orNull(f.expected_operational),
        actual_delivery: orNull(f.actual_delivery), actual_operational: orNull(f.actual_operational), notes: orNull(f.notes),
      };
      return lot
        ? api.patch<SupplyOrder>(`/v1/capacity/orders/${order.id}/lots/${lot.id}`, body)
        : api.post<SupplyOrder>(`/v1/capacity/orders/${order.id}/lots`, body);
    },
    onSuccess: () => { toast.success('Lot saved'); onSaved(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save the lot')),
  });
  const del = useMutation({
    mutationFn: () => api.del<SupplyOrder>(`/v1/capacity/orders/${order.id}/lots/${lot!.id}`),
    onSuccess: () => { toast.success('Lot removed'); onSaved(); },
    onError: (e) => toast.error(errMessage(e, 'Could not remove the lot')),
  });
  return (
    <Modal open onClose={onClose} title={lot ? `Edit ${lot.lot_label ?? 'lot'}` : `Add lot to ${order.reference}`}>
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label" htmlFor="lot_label">Name</label><input id="lot_label" className="input" value={f.label} onChange={set('label')} /></div>
          <div><label className="label" htmlFor="lot_servers">Servers (max {n(maxServers)})</label>
            <input id="lot_servers" className="input" type="number" min={1} max={maxServers} required value={f.servers} onChange={set('servers')} />
            <span className="text-xs text-grape-soft">{n((Number(f.servers) || 0) * order.gpus_per_server)} GPUs</span></div>
          <div><label className="label" htmlFor="lot_status">Status</label>
            <select id="lot_status" className="input" value={f.status} onChange={set('status')}>
              {PROCUREMENT_STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select></div>
          <div><label className="label" htmlFor="lot_ed">Expected delivery</label><input id="lot_ed" className="input" type="date" value={f.expected_delivery} onChange={set('expected_delivery')} /></div>
          <div><label className="label" htmlFor="lot_eo">Expected operational</label><input id="lot_eo" className="input" type="date" value={f.expected_operational} onChange={set('expected_operational')} /></div>
          <div />
          <div><label className="label" htmlFor="lot_ad">Delivered on</label><input id="lot_ad" className="input" type="date" value={f.actual_delivery} onChange={set('actual_delivery')} /></div>
          <div><label className="label" htmlFor="lot_ao">Operational on</label><input id="lot_ao" className="input" type="date" value={f.actual_operational} onChange={set('actual_operational')} /></div>
        </div>
        <div><label className="label" htmlFor="lot_notes">Notes</label><textarea id="lot_notes" className="input" rows={2} value={f.notes} onChange={set('notes')} /></div>
        <div className="flex justify-end gap-3">
          {lot && <button type="button" className="btn-ghost mr-auto text-flamingo" disabled={del.isPending}
            onClick={() => { if (confirm('Remove this lot? Its GPUs go back to “no date yet”.')) del.mutate(); }}>Remove lot</button>}
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save lot'}</button>
        </div>
      </form>
    </Modal>
  );
}
