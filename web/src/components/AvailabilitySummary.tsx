// Sales Pipeline: what we can offer right now and in the coming months, with a button for the full list.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast } from './toast';
import { Badge, Modal } from './ui';
import { copyAvailabilityText, model, n, priceText, unit, when, type Offer } from './AvailabilityList';

/** One line per term: "36 mo US$ 6.44 – 6.80". */
const tierLines = (o: Offer): string[] => {
  const by = new Map<number, number[]>();
  for (const r of o.rates ?? []) by.set(r.term_months, [...(by.get(r.term_months) ?? []), Number(r.price_per_gpu_hour)]);
  return [...by.entries()].sort((a, b) => b[0] - a[0]).map(([term, v]) => {
    const lo = Math.min(...v).toFixed(2), hi = Math.max(...v).toFixed(2);
    return `${term} mo  US$ ${lo === hi ? lo : `${lo} – ${hi}`}`;
  });
};
const monthShort = (d: string) => {
  const [y, m] = d.split('-');
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short' });
};
const qty = (gpus: number, racks: number) =>
  [gpus ? `${n(gpus)} GPUs` : '', racks ? `${n(racks)} racks` : ''].filter(Boolean).join(' + ');

export default function AvailabilitySummary() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const allowed = hasPermission('capacity.read');
  const q = useQuery({
    queryKey: ['capacity', 'availability'], queryFn: () => api.get<Offer[]>('/v1/capacity/availability'), enabled: allowed,
  });
  const offers = q.data ?? [];

  const { now, months, groups } = useMemo(() => {
    const nowBy = new Map<string, Offer[]>();
    const monthsBy = new Map<string, { gpus: number; racks: number }>();
    const groupsBy = new Map<string, Offer[]>();
    for (const o of offers) {
      const key = o.available_from ?? 'now';
      groupsBy.set(key, [...(groupsBy.get(key) ?? []), o]);
      if (!o.available_from) { nowBy.set(model(o), [...(nowBy.get(model(o)) ?? []), o]); continue; }
      const cur = monthsBy.get(o.available_from) ?? { gpus: 0, racks: 0 };
      if (o.quantity_unit === 'RACKS') cur.racks += o.available_qty; else cur.gpus += o.available_qty;
      monthsBy.set(o.available_from, cur);
    }
    const sortKeys = (m: Map<string, unknown>) => [...m.keys()].sort();
    return {
      now: [...nowBy.entries()].map(([m, rows]) => ({
        model: m, gpus: rows.filter((o) => o.quantity_unit === 'GPUS').reduce((s, o) => s + o.available_qty, 0),
        racks: rows.filter((o) => o.quantity_unit === 'RACKS').reduce((s, o) => s + o.available_qty, 0),
        sites: [...new Set(rows.map((o) => o.site))].join(', '),
      })),
      months: sortKeys(monthsBy).map((k) => ({ key: k, ...monthsBy.get(k)! })),
      groups: [...groupsBy.keys()].sort((a, b) => (a === 'now' ? -1 : b === 'now' ? 1 : a.localeCompare(b))).map((k) => ({ key: k, rows: groupsBy.get(k)! })),
    };
  }, [offers]);

  if (!allowed) return null;
  return (
    <section className="card flex flex-col gap-3 p-4" data-testid="availability-summary">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="eyebrow">AVAILABILITY · WHAT WE CAN OFFER</span>
        <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={() => setOpen(true)} data-testid="availability-open">
          View availability
        </button>
      </div>
      {q.isLoading ? <p className="text-sm text-grape-soft">Loading availability…</p> : offers.length === 0 ? (
        <p className="text-sm text-grape-soft">No availability listed yet. Add it on the Capacity page.</p>
      ) : (
        <div className="flex flex-col gap-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-24 shrink-0 text-xs text-grape-soft">Available now</span>
            {now.length === 0 ? <span className="text-grape-soft">Nothing immediate</span> : now.map((x) => (
              <span key={x.model} className="rounded-full border border-cyan/40 px-2.5 py-0.5 text-xs" title={x.sites}>
                <span className="font-semibold text-white">{x.model}</span>{' '}
                <span className="text-cyan">{qty(x.gpus, x.racks)}</span>
                <span className="text-grape-soft"> · {x.sites}</span>
              </span>
            ))}
          </div>
          {months.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-24 shrink-0 text-xs text-grape-soft">Coming</span>
              {months.map((m) => (
                <span key={m.key} className="rounded-full border border-white/10 px-2.5 py-0.5 text-xs">
                  <span className="text-grape-soft">{monthShort(m.key)}</span> <span className="text-white">{qty(m.gpus, m.racks)}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Availability" size="wide">
        <div className="flex flex-col gap-5" data-testid="availability-modal">
          {groups.map((g) => (
            <div key={g.key} className="flex flex-col gap-2">
              <div><Badge tone={g.key === 'now' ? 'success' : 'grape'}>{when(g.key === 'now' ? null : g.key)}</Badge></div>
              <div className="table-wrap overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-grape-soft">
                      <th className="py-1 pr-3 font-normal">GPU model</th><th className="py-1 pr-3 font-normal">Site</th>
                      <th className="py-1 pr-3 text-right font-normal">Total</th><th className="py-1 pr-3 text-right font-normal">Available</th>
                      <th className="py-1 text-right font-normal">Price / GPU-hour</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.rows.map((o) => (
                      <tr key={o.id} className="border-t border-white/5">
                        <td className="py-1.5 pr-3 font-medium text-white">{model(o)}</td>
                        <td className="py-1.5 pr-3">{o.site}</td>
                        <td className="py-1.5 pr-3 text-right">{o.total_qty != null ? `${n(o.total_qty)} ${unit(o)}` : '—'}</td>
                        <td className="py-1.5 pr-3 text-right font-semibold text-cyan">{n(o.available_qty)} {unit(o)}</td>
                        <td className="py-1.5 text-right">
                          {o.price_per_gpu_hour != null ? priceText(o) : o.rates?.length
                            ? tierLines(o).map((l) => <div key={l} className="whitespace-nowrap">{l}</div>)
                            : <span className="text-grape-soft">on request</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {offers.length === 0 && <p className="text-sm text-grape-soft">No availability listed yet.</p>}
          <p className="text-xs text-grape-soft">
            Prices per GPU-hour by term, depending on the upfront share (35% to 65%; VR200 40%). They apply to orders of
            at least 32 servers (256 GPUs); smaller orders need an administrator's approval. GPUs are sold in multiples of 8.
          </p>
          <div className="flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => copyAvailabilityText(toast)}>Copy as text</button>
            <button type="button" className="btn-primary" onClick={() => setOpen(false)}>Close</button>
          </div>
        </div>
      </Modal>
    </section>
  );
}
