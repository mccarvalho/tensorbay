// Pipeline board — a Kanban view of opportunities, one column per sales stage.
// Drag a card to another column to move the deal; the "Move to" menu on each card
// does the same for keyboard and touch users (native drag & drop is mouse-only).
import { useMemo, useRef, useState, type DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { Badge, type BadgeTone } from '../components/ui';
import { STAGE_HINT, stageLabel, type SalesStage } from '../salesStages';

export type BoardStage = string;

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
  sales_stage: BoardStage;
  account_owner: string | null;
}

interface Props {
  stages: BoardStage[];
  tones: Record<string, BadgeTone>;
  opportunities: BoardOpportunity[];
  customerName: (customerId: string) => string;
  /** False = read-only board (no dragging, no move menu, no add buttons). */
  canWrite: boolean;
  /** Id of a card whose move request is in flight. */
  busyId?: string | null;
  onMove: (opportunity: BoardOpportunity, stage: BoardStage) => void;
  onEdit: (opportunity: BoardOpportunity) => void;
  onQuotes: (opportunity: BoardOpportunity) => void;
  onAdd: (stage: BoardStage) => void;
}

const usd = (v: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v);

const label = stageLabel;

export default function PipelineBoard({
  stages, tones, opportunities, customerName, canWrite, busyId, onMove, onEdit, onQuotes, onAdd,
}: Props) {
  // The id lives in a ref as well as state: `dragover` can fire before React has
  // re-rendered after `dragstart`, and the handlers must already know a drag is on.
  const dragRef = useRef<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overStage, setOverStage] = useState<string | null>(null);

  const byStage = useMemo(() => {
    const map: Record<string, BoardOpportunity[]> = Object.fromEntries(stages.map((s) => [s, []]));
    for (const o of opportunities) (map[o.sales_stage] ??= []).push(o);
    // Biggest deals first inside each column.
    for (const list of Object.values(map)) list.sort((a, b) => Number(b.expected_mrr) - Number(a.expected_mrr));
    return map;
  }, [opportunities, stages]);

  const byId = useMemo(() => new Map(opportunities.map((o) => [o.id, o])), [opportunities]);

  function drop(e: DragEvent, stage: BoardStage) {
    e.preventDefault();
    const id = dragRef.current || e.dataTransfer.getData('text/plain');
    dragRef.current = null;
    setDragId(null);
    setOverStage(null);
    const opp = id ? byId.get(id) : undefined;
    if (opp && opp.sales_stage !== stage) onMove(opp, stage);
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-3" data-testid="pipeline-board">
      {stages.map((stage) => {
        const cards = byStage[stage] ?? [];
        const mrr = cards.reduce((s, o) => s + Number(o.expected_mrr), 0);
        const hot = overStage === stage && dragId !== null;
        return (
          <section
            key={stage}
            data-testid={`column-${stage}`}
            aria-label={`${label(stage)} column`}
            onDragOver={(e) => {
              if (!canWrite || !dragRef.current) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = 'move';
              if (overStage !== stage) setOverStage(stage);
            }}
            onDragLeave={(e) => {
              // Ignore leave events fired when moving between the column's own children.
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOverStage(null);
            }}
            onDrop={(e) => canWrite && drop(e, stage)}
            className={`flex min-w-[200px] flex-1 basis-[200px] flex-col gap-3 rounded-2xl border p-3 transition-colors ${
              hot ? 'border-cyan bg-cyan/5' : 'border-white/10 bg-white/[0.02]'
            }`}
          >
            <header className="flex items-start justify-between gap-2">
              <div className="flex flex-col gap-1">
                <span title={STAGE_HINT[stage as SalesStage] ?? ''}><Badge tone={tones[stage] ?? 'neutral'}>{label(stage)}</Badge></span>
                <span className="text-xs text-grape-soft">
                  {cards.length} {cards.length === 1 ? 'deal' : 'deals'} · {usd(mrr)} MRR
                </span>
              </div>
              {canWrite && (
                <button
                  type="button"
                  className="btn-ghost px-2 py-0.5 text-sm"
                  aria-label={`Add opportunity to ${label(stage)}`}
                  title={`New opportunity in ${label(stage)}`}
                  onClick={() => onAdd(stage)}
                >
                  +
                </button>
              )}
            </header>

            <div className="flex max-h-[62vh] min-h-[60px] flex-col gap-2 overflow-y-auto pr-0.5">
              {cards.length === 0 && (
                <p className="rounded-xl border border-dashed border-white/10 p-3 text-center text-xs text-grape-soft">
                  {canWrite ? 'Drop a deal here' : 'No deals'}
                </p>
              )}
              {cards.map((o) => (
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
                  onDragEnd={() => { dragRef.current = null; setDragId(null); setOverStage(null); }}
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
                    {o.quantity.toLocaleString('en-US')} × {o.commercial_model} · {o.duration_months} mo
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-cyan">{usd(Number(o.expected_mrr))}</span>
                    <span className="text-xs text-grape-soft">{o.probability}%</span>
                  </div>
                  <div className="truncate text-xs text-grape-soft">{o.account_owner ?? 'No owner'}</div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Link to={`/opportunities/${o.id}`} className="btn-ghost px-2 py-0.5 text-xs">View</Link>
                    <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => onQuotes(o)}>Quotes</button>
                    {canWrite && (
                      <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => onEdit(o)}>Edit</button>
                    )}
                    {canWrite && (
                      <select
                        aria-label={`Move ${customerName(o.customer_id)} to stage`}
                        className="input ml-auto max-w-[110px] py-0.5 text-xs"
                        value={o.sales_stage}
                        disabled={busyId === o.id}
                        onChange={(e) => { if (e.target.value !== o.sales_stage) onMove(o, e.target.value); }}
                      >
                        {stages.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                      </select>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
