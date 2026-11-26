// What sales can offer now and by month, per GPU model and site, with an optional price per GPU-hour.
// "Copy as text" gives the list in the format sent to customers (prices included where set).
import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { GPU_MODELS } from '../constants';
import { useToast, errMessage } from './toast';
import { DataTable, EmptyState, ErrorState, Modal, Spinner, type Column } from './ui';

interface Offer {
  id: string; gpu_model: string; cooling: 'AIR' | 'LIQUID' | null; quantity_unit: 'GPUS' | 'RACKS'; site: string;
  available_from: string | null; total_qty: number | null; available_qty: number;
  price_per_gpu_hour: string | null; currency: string; notes: string | null;
}

const n = (v: number) => v.toLocaleString('en-US');
const unit = (o: Offer) => (o.quantity_unit === 'RACKS' ? 'racks' : 'GPUs');
const when = (d: string | null) => {
  if (!d) return 'Immediate';
  const [y, m] = d.split('-');
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
};
const model = (o: Offer) => o.gpu_model + (o.cooling === 'AIR' ? ' · Air' : o.cooling === 'LIQUID' ? ' · Liquid' : '');

export default function AvailabilityList() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('inventory.write');
  const [editing, setEditing] = useState<Offer | 'new' | null>(null);
  const list = useQuery({ queryKey: ['capacity', 'availability'], queryFn: () => api.get<Offer[]>('/v1/capacity/availability') });
  const refresh = () => { qc.invalidateQueries({ queryKey: ['capacity', 'availability'] }); };
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/capacity/availability/${id}`),
    onSuccess: () => { refresh(); toast.success('Entry deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete')),
  });
  const copy = async () => {
    try {
      const r = await api.get<{ text: string }>('/v1/capacity/availability/text');
      await navigator.clipboard.writeText(r.text);
      toast.success('List copied');
    } catch (e) { toast.error(errMessage(e, 'Could not copy the list')); }
  };

  const cols: Array<Column<Offer>> = [
    { key: 'w', header: 'Available from', render: (o) => <span className={o.available_from ? '' : 'text-emerald-300'}>{when(o.available_from)}</span> },
    { key: 'm', header: 'GPU model', render: (o) => <span className="font-medium text-white">{model(o)}</span> },
    { key: 's', header: 'Site', render: (o) => o.site },
    { key: 't', header: 'Total', className: 'text-right', render: (o) => (o.total_qty != null ? `${n(o.total_qty)} ${unit(o)}` : '—') },
    { key: 'a', header: 'Available now', className: 'text-right', render: (o) => <span className="font-semibold text-cyan">{n(o.available_qty)} {unit(o)}</span> },
    { key: 'p', header: 'Price / GPU-hour', className: 'text-right', render: (o) => (o.price_per_gpu_hour != null
      ? <span>{o.currency === 'USD' ? 'US$' : o.currency} {Number(o.price_per_gpu_hour).toFixed(2)}</span> : <span className="text-grape-soft">no price</span>) },
    ...(canWrite ? [{ key: 'x', header: '', className: 'text-right', render: (o: Offer) => (
      <span className="flex justify-end gap-2">
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setEditing(o)}>Edit</button>
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
          onClick={() => { if (confirm(`Delete ${model(o)} at ${o.site}?`)) del.mutate(o.id); }}>Delete</button>
      </span>
    ) } as Column<Offer>] : []),
  ];

  return (
    <section className="flex flex-col gap-4" data-testid="availability-list">
      <div className="flex items-center justify-between">
        <span className="eyebrow">AVAILABILITY · WHAT WE CAN OFFER</span>
        <span className="flex gap-2">
          <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={copy}>Copy as text</button>
          {canWrite && <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => setEditing('new')}>+ Add availability</button>}
        </span>
      </div>
      {list.isLoading ? <Spinner label="Loading availability…" /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(o) => o.id}
          empty={<EmptyState title="No availability listed" hint="Add the GPUs you can offer now and by month, with the site and the price." />} />
      )}
      {editing && <OfferModal offer={editing === 'new' ? null : editing} onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); refresh(); }} />}
    </section>
  );
}

function OfferModal({ offer, onClose, onSaved }: { offer: Offer | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({
    gpu_model: offer?.gpu_model ?? '', cooling: offer?.cooling ?? '', quantity_unit: offer?.quantity_unit ?? 'GPUS',
    site: offer?.site ?? '', month: offer?.available_from?.slice(0, 7) ?? '',
    total_qty: offer?.total_qty != null ? String(offer.total_qty) : '', available_qty: offer ? String(offer.available_qty) : '',
    price: offer?.price_per_gpu_hour != null ? String(Number(offer.price_per_gpu_hour)) : '', notes: offer?.notes ?? '',
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        gpu_model: f.gpu_model.trim(), cooling: f.cooling || null, quantity_unit: f.quantity_unit, site: f.site.trim(),
        available_from: f.month ? `${f.month}-01` : null, total_qty: f.total_qty === '' ? null : Number(f.total_qty),
        available_qty: Number(f.available_qty), price_per_gpu_hour: f.price === '' ? null : f.price, notes: f.notes.trim() || null,
      };
      return offer ? api.patch<Offer>(`/v1/capacity/availability/${offer.id}`, body) : api.post<Offer>('/v1/capacity/availability', body);
    },
    onSuccess: () => { toast.success('Availability saved'); onSaved(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save')),
  });
  return (
    <Modal open onClose={onClose} title={offer ? 'Edit availability' : 'Add availability'}>
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><label className="label" htmlFor="av_model">GPU model</label>
            <input id="av_model" className="input" list="av-models" required value={f.gpu_model} onChange={set('gpu_model')} />
            <datalist id="av-models">{GPU_MODELS.map((m) => <option key={m} value={m} />)}</datalist></div>
          <div><label className="label" htmlFor="av_cool">Cooling</label>
            <select id="av_cool" className="input" value={f.cooling} onChange={set('cooling')}>
              <option value="">—</option><option value="AIR">Air</option><option value="LIQUID">Liquid</option></select></div>
          <div><label className="label" htmlFor="av_unit">Counted in</label>
            <select id="av_unit" className="input" value={f.quantity_unit} onChange={set('quantity_unit')}>
              <option value="GPUS">GPUs</option><option value="RACKS">Racks</option></select></div>
          <div><label className="label" htmlFor="av_site">Site</label>
            <input id="av_site" className="input" required value={f.site} onChange={set('site')} placeholder="Brazil, Chicago US…" /></div>
          <div><label className="label" htmlFor="av_month">Available from (month)</label>
            <input id="av_month" className="input" type="month" value={f.month} onChange={set('month')} />
            <span className="text-xs text-grape-soft">Blank = immediate</span></div>
          <div><label className="label" htmlFor="av_price">Price per GPU-hour (US$)</label>
            <input id="av_price" className="input" type="number" min={0} step="0.0001" value={f.price} onChange={set('price')} /></div>
          <div><label className="label" htmlFor="av_total">Total</label>
            <input id="av_total" className="input" type="number" min={0} value={f.total_qty} onChange={set('total_qty')} /></div>
          <div><label className="label" htmlFor="av_avail">Available at the moment</label>
            <input id="av_avail" className="input" type="number" min={0} required value={f.available_qty} onChange={set('available_qty')} /></div>
        </div>
        <div><label className="label" htmlFor="av_notes">Notes</label><textarea id="av_notes" className="input" rows={2} value={f.notes} onChange={set('notes')} /></div>
        <div className="flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </Modal>
  );
}
