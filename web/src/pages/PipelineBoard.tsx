// Pipeline board — a Kanban view of opportunities in five macro stages, each owned
// by a department and split into substages. Two groupings:
//   • stage: one column per macro stage (+ On Hold, Lost); substage rows in each header
//   • inventory: one lane per GPU model, so sales can see stock and incoming supply
//     before promising capacity.
// Drag a card onto a substage row (or a column / cell, which means "first substage")
// to move the deal; the "Move to" menu on each card does the same for keyboard and
// touch users (native drag & drop is mouse-only).
import { useMemo, useRef, useState, type DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui';
import {
  ESCROW_STAGES, MACRO_STAGES, STAGE_HINT, STAGE_LABEL, STAGE_TONE, macroOf, stageLabel,
  type MacroStage, type SalesStage,
} from '../salesStages';

export interface BoardOpportunity {
  id: string;
  customer_id: string;
  short_name?: string | null;
  gpu_model: string;
  quantity: number;
  duration_months: number;
  commercial_model: string;
  expected_mrr: string | number;
  probability: number;
  sales_stage: string;
  account_owner: string | null;
  region?: string | null;
  assigned_to?: string | null;
  next_action?: string | null;
  expected_start?: string | null;
  escrow_required?: boolean;
}

export interface InventoryLane {
  gpu_model: string;
  physical: number;
  allocated: number;
  reserved: number;
  available: number;
  incoming: number;
  open_demand: number;
}

interface Props {
  mode: 'stage' | 'inventory';
  opportunities: BoardOpportunity[];
  lanes: InventoryLane[];
  /** Only show this macro stage (stage mode); null = all. */
  macroFilter: MacroStage['key'] | null;
  customerName: (customerId: string) => string;
  /** False = read-only board (no dragging, no move menu, no add buttons). */
  canWrite: boolean;
  /** Id of a card whose move request is in flight. */
  busyId?: string | null;
  onMove: (opportunity: BoardOpportunity, stage: SalesStage) => void;
  onEdit: (opportunity: BoardOpportunity) => void;
  onQuotes: (opportunity: BoardOpportunity) => void;
  onAdd: (stage: SalesStage) => void;
}

const usd = (v: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v);

const shortDate = (iso: string): string =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

const stageOrder = (s: string): number => {
  const i = MACRO_STAGES.flatMap((m) => m.stages).indexOf(s as SalesStage);
  return i < 0 ? 99 : i;
};

export default function PipelineBoard({
  mode, opportunities, lanes, macroFilter, customerName, canWrite, busyId, onMove, onEdit, onQuotes, onAdd,
}: Props) {
  // The id lives in a ref as well as state: `dragover` can fire before React has
  // re-rendered after `dragstart`, and the handlers must already know a drag is on.
  const dragRef = useRef<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);

  const byId = useMemo(() => new Map(opportunities.map((o) => [o.id, o])), [opportunities]);

  const sortCards = (list: BoardOpportunity[]) =>
    [...list].sort((a, b) => stageOrder(a.sales_stage) - stageOrder(b.sales_stage) || Number(b.expected_mrr) - Number(a.expected_mrr));

  function drop(e: DragEvent, stage: SalesStage) {
    e.preventDefault();
    e.stopPropagation();
    const id = dragRef.current || e.dataTransfer.getData('text/plain');
    dragRef.current = null;
    setDragId(null);
    setOver(null);
    const opp = id ? byId.get(id) : undefined;
    if (opp && opp.sales_stage !== stage) onMove(opp, stage);
  }

  /** Drop-target props for an area that moves a card to `stage`. */
  const target = (key: string, stage: SalesStage) => ({
    onDragOver: (e: DragEvent) => {
      if (!canWrite || !dragRef.current) return;
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'move';
      if (over !== key) setOver(key);
    },
    onDragLeave: (e: DragEvent) => {
      // Ignore leave events fired when moving between the area's own children.
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver((k) => (k === key ? null : k));
    },
    onDrop: (e: DragEvent) => canWrite && drop(e, stage),
  });

  const hot = (key: string) => over === key && dragId !== null;

  function card(o: BoardOpportunity) {
    const macro = macroOf(o.sales_stage);
    const noEscrow = o.escrow_required === false;
    return (
      <article
        key={o.id}
        data-testid={`card-${o.id}`}
        draggable={canWrite && busyId !== o.id}
        onDragStart={(e) => {
          e.dataTransfer.setData('text/plain', o.id);
          e.dataTransfer.effectAllowed = 'move';
          dragRef.current = o.id;
          setDragId(o.id);
        }}
        onDragEnd={() => { dragRef.current = null; setDragId(null); setOver(null); }}
        className={`card flex flex-col gap-2 p-3 ${canWrite ? 'cursor-grab active:cursor-grabbing' : ''} ${
          dragId === o.id ? 'opacity-40' : ''
        } ${busyId === o.id ? 'animate-pulse' : ''}`}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="font-semibold leading-snug text-white">{customerName(o.customer_id)}</span>
          <Badge tone="grape">{o.gpu_model}</Badge>
        </div>
        {o.short_name && <div className="-mt-1 text-sm text-cyan">{o.short_name}</div>}
        <div className="text-xs text-grape-soft">
          {o.quantity.toLocaleString('en-US')} GPUs{o.region ? ` · ${o.region}` : ''} · {o.duration_months} mo
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-cyan">{usd(Number(o.expected_mrr))}<span className="text-xs font-normal text-grape-soft"> MRR</span></span>
          <span className="text-xs text-grape-soft">{o.probability}%</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span title={STAGE_HINT[o.sales_stage as SalesStage] ?? ''}>
            <Badge tone={STAGE_TONE[o.sales_stage as SalesStage] ?? 'neutral'}>{stageLabel(o.sales_stage)}</Badge>
          </span>
          <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-grape-soft">{o.commercial_model}</span>
          <span className={`rounded-full border px-2 py-0.5 text-[11px] ${noEscrow ? 'border-white/10 text-grape-soft' : 'border-cyan/40 text-cyan'}`}>
            {noEscrow ? 'No escrow' : 'Escrow'}
          </span>
        </div>
        <div className="text-xs text-grape-soft">
          <div className="truncate">Owner: <span className="text-white">{o.account_owner ?? '—'}</span></div>
          <div className="truncate">
            Assigned: <span className="text-white">{macro?.department.split(' · ')[0] ?? '—'}</span>
            {o.assigned_to ? ` (${o.assigned_to})` : ''}
          </div>
          {o.expected_start && <div>Start: {shortDate(o.expected_start)}</div>}
          {o.next_action && <div className="truncate" title={o.next_action}>Next: <span className="text-white">{o.next_action}</span></div>}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Link to={`/opportunities/${o.id}`} className="btn-ghost px-2 py-0.5 text-xs">View</Link>
          <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => onQuotes(o)}>Quotes</button>
          {canWrite && (
            <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => onEdit(o)}>Edit</button>
          )}
          {canWrite && (
            <select
              aria-label={`Move ${customerName(o.customer_id)} to stage`}
              className="input ml-auto max-w-[120px] py-0.5 text-xs"
              value={o.sales_stage}
              disabled={busyId === o.id}
              onChange={(e) => { if (e.target.value !== o.sales_stage) onMove(o, e.target.value as SalesStage); }}
            >
              {MACRO_STAGES.map((m) => (
                <optgroup key={m.key} label={`${m.n}. ${m.label}`}>
                  {m.stages.map((s) => (
                    <option key={s} value={s} disabled={noEscrow && ESCROW_STAGES.includes(s)}>{STAGE_LABEL[s]}</option>
                  ))}
                </optgroup>
              ))}
              <option value="ON_HOLD">On Hold</option>
              <option value="LOST">Lost</option>
            </select>
          )}
        </div>
      </article>
    );
  }

  // ------------------------------------------------------------------ inventory
  if (mode === 'inventory') {
    const cols = MACRO_STAGES;
    const grid = { gridTemplateColumns: `220px repeat(${cols.length}, minmax(210px, 1fr))` };
    const cellDeals = (model: string, m: MacroStage) =>
      sortCards(opportunities.filter((o) => o.gpu_model === model && (m.stages as string[]).includes(o.sales_stage)));
    return (
      <div className="overflow-x-auto pb-3" data-testid="pipeline-board">
        <div className="grid min-w-max gap-3" style={grid}>
          <div />
          {cols.map((m) => (
            <div key={m.key} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
              <div className="flex items-center gap-2"><Badge tone={m.tone}>{m.n}. {m.label}</Badge></div>
              <div className="mt-1 text-xs text-grape-soft">{m.department}</div>
            </div>
          ))}
          {lanes.map((lane) => {
            const short = lane.open_demand - lane.available - lane.incoming;
            return (
              <div key={lane.gpu_model} className="contents" data-testid={`lane-${lane.gpu_model}`}>
                <div className="flex flex-col gap-1 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-grape-soft">
                  <div className="text-base font-semibold text-white">{lane.gpu_model}</div>
                  <div>Physical: <span className="text-white">{lane.physical.toLocaleString('en-US')}</span></div>
                  <div>Allocated: <span className="text-white">{lane.allocated.toLocaleString('en-US')}</span> · Reserved: <span className="text-white">{lane.reserved.toLocaleString('en-US')}</span></div>
                  <div>Available: <span className="font-semibold text-cyan">{lane.available.toLocaleString('en-US')}</span></div>
                  <div>Incoming: <span className="text-white">{lane.incoming.toLocaleString('en-US')}</span></div>
                  <div>Open demand: <span className="text-white">{lane.open_demand.toLocaleString('en-US')}</span></div>
                  {short > 0 ? (
                    <div className="mt-1 rounded-lg bg-flamingo/15 px-2 py-1 text-flamingo" data-testid={`short-${lane.gpu_model}`}>
                      Short by {short.toLocaleString('en-US')} GPUs. Check with Procurement
                    </div>
                  ) : (
                    <div className="mt-1 text-cyan">Covered by stock and incoming supply</div>
                  )}
                </div>
                {cols.map((m) => {
                  const key = `cell-${lane.gpu_model}-${m.key}`;
                  const deals = cellDeals(lane.gpu_model, m);
                  return (
                    <div
                      key={key}
                      data-testid={key}
                      {...target(key, m.stages[0])}
                      className={`flex min-h-[90px] flex-col gap-2 rounded-xl border p-2 transition-colors ${
                        hot(key) ? 'border-cyan bg-cyan/5' : 'border-white/10 bg-white/[0.02]'
                      }`}
                    >
                      {deals.length === 0 && (
                        <p className="m-auto text-center text-xs text-grape-soft">{canWrite ? 'Drop a deal here' : '—'}</p>
                      )}
                      {deals.map(card)}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        {lanes.length === 0 && <p className="p-4 text-sm text-grape-soft">No GPU models yet.</p>}
        <p className="mt-2 text-xs text-grape-soft">On Hold and Lost deals are not shown in this view. Dropping on a cell moves the deal to the first substage of that stage.</p>
      </div>
    );
  }

  // ---------------------------------------------------------------------- stage
  const visible = macroFilter ? MACRO_STAGES.filter((m) => m.key === macroFilter) : MACRO_STAGES;
  const showOutside = !macroFilter;
  const outside: Array<{ key: 'ON_HOLD' | 'LOST'; stage: SalesStage }> = showOutside
    ? [{ key: 'ON_HOLD', stage: 'ON_HOLD' }, { key: 'LOST', stage: 'LOST' }]
    : [];

  return (
    <div className="flex gap-4 overflow-x-auto pb-3" data-testid="pipeline-board">
      {visible.map((m) => {
        const cards = sortCards(opportunities.filter((o) => (m.stages as string[]).includes(o.sales_stage)));
        const mrr = cards.reduce((s, o) => s + Number(o.expected_mrr), 0);
        const colKey = `col-${m.key}`;
        return (
          <section
            key={m.key}
            data-testid={`column-${m.key}`}
            aria-label={`${m.label} column`}
            {...target(colKey, m.stages[0])}
            className={`flex min-w-[230px] flex-1 basis-[230px] flex-col gap-3 rounded-2xl border p-3 transition-colors ${
              hot(colKey) ? 'border-cyan bg-cyan/5' : 'border-white/10 bg-white/[0.02]'
            }`}
          >
            <header className="flex flex-col gap-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex flex-col gap-1">
                  <Badge tone={m.tone}>{m.n}. {m.label}</Badge>
                  <span className="text-[11px] text-grape-soft">{m.department}</span>
                  <span className="text-xs text-grape-soft">
                    {cards.length} {cards.length === 1 ? 'deal' : 'deals'} · {usd(mrr)} MRR
                  </span>
                </div>
                {canWrite && (
                  <button
                    type="button"
                    className="btn-ghost px-2 py-0.5 text-sm"
                    aria-label={`Add opportunity to ${m.label}`}
                    title={`New opportunity in ${m.label}`}
                    onClick={() => onAdd(m.stages[0])}
                  >
                    +
                  </button>
                )}
              </div>
              <ul className="flex flex-col gap-1">
                {m.stages.map((s) => {
                  const n = cards.filter((o) => o.sales_stage === s).length;
                  const key = `sub-${s}`;
                  return (
                    <li
                      key={s}
                      data-testid={`substage-${s}`}
                      title={STAGE_HINT[s]}
                      {...target(key, s)}
                      className={`flex items-center justify-between rounded-lg border px-2 py-1 text-xs ${
                        hot(key) ? 'border-cyan bg-cyan/10 text-white' : 'border-white/10 text-grape-soft'
                      }`}
                    >
                      <span>{STAGE_LABEL[s]}</span>
                      <span className={n ? 'font-semibold text-white' : ''}>{n}</span>
                    </li>
                  );
                })}
              </ul>
            </header>
            <div className="flex max-h-[62vh] min-h-[60px] flex-col gap-2 overflow-y-auto pr-0.5">
              {cards.length === 0 && (
                <p className="rounded-xl border border-dashed border-white/10 p-3 text-center text-xs text-grape-soft">
                  {canWrite ? 'Drop a deal here' : 'No deals'}
                </p>
              )}
              {cards.map(card)}
            </div>
          </section>
        );
      })}
      {outside.map(({ key, stage }) => {
        const cards = sortCards(opportunities.filter((o) => o.sales_stage === stage));
        const colKey = `col-${key}`;
        return (
          <section
            key={key}
            data-testid={`column-${key}`}
            aria-label={`${STAGE_LABEL[stage]} column`}
            {...target(colKey, stage)}
            className={`flex min-w-[200px] basis-[200px] flex-col gap-3 rounded-2xl border p-3 transition-colors ${
              hot(colKey) ? 'border-cyan bg-cyan/5' : 'border-white/10 bg-white/[0.02]'
            }`}
          >
            <header className="flex flex-col gap-1">
              <Badge tone={STAGE_TONE[stage]}>{STAGE_LABEL[stage]}</Badge>
              <span className="text-xs text-grape-soft">{cards.length} {cards.length === 1 ? 'deal' : 'deals'}</span>
            </header>
            <div className="flex max-h-[62vh] min-h-[60px] flex-col gap-2 overflow-y-auto pr-0.5">
              {cards.length === 0 && (
                <p className="rounded-xl border border-dashed border-white/10 p-3 text-center text-xs text-grape-soft">
                  {canWrite ? 'Drop a deal here' : 'No deals'}
                </p>
              )}
              {cards.map(card)}
            </div>
          </section>
        );
      })}
    </div>
  );
}
