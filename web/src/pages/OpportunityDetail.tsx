// Opportunity detail / drill-down — plan §9 funnel.
// Opportunity summary + its quotes (with per-SKU line items). Links to the
// owning customer. Read-focused.
import { Link, useParams } from 'react-router-dom';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  KpiCard,
  type BadgeTone,
  type Column,
} from '../components/ui';

type SalesStage = 'PROSPECTING' | 'QUALIFICATION' | 'PROPOSAL' | 'NEGOTIATION' | 'WON' | 'LOST';
type QuoteStatus = 'DRAFT' | 'SENT' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED';

interface Opportunity {
  id: string; customer_id: string; gpu_model: string; quantity: number;
  expected_start: string | null; duration_months: number; commercial_model: string;
  expected_mrr: string | number; probability: number; sales_stage: SalesStage;
  account_owner: string | null; account_owner_email: string | null;
}
interface QuoteItem { id: string; sku_id: string; quantity: number; unit_price: string | number; discount_pct: string | number }
interface Quote {
  id: string; opportunity_id: string; quote_number: string; status: QuoteStatus;
  term_months: number; total_amount: string | number; valid_until: string | null; items: QuoteItem[];
}
interface Sku { id: string; code: string; name: string }
interface CustomerLite { id: string; legal_name: string }

const STAGE_TONE: Record<SalesStage, BadgeTone> = {
  PROSPECTING: 'neutral', QUALIFICATION: 'cyan', PROPOSAL: 'grape', NEGOTIATION: 'warning', WON: 'success', LOST: 'flamingo',
};
const QUOTE_TONE: Record<QuoteStatus, BadgeTone> = {
  DRAFT: 'neutral', SENT: 'cyan', ACCEPTED: 'success', REJECTED: 'flamingo', EXPIRED: 'neutral',
};
const money = (v: string | number) =>
  Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });

export default function OpportunityDetail() {
  const { id = '' } = useParams();

  const oppQuery = useQuery({
    queryKey: ['opportunity', id],
    queryFn: () => api.get<Opportunity>(`/v1/sales/opportunities/${id}`),
    enabled: id.length > 0,
  });
  const quotesQuery = useQuery({
    queryKey: ['quotes', 'byOpp', id],
    queryFn: () => api.get<Quote[]>(`/v1/sales/quotes?opportunity_id=${id}&limit=200`),
    enabled: id.length > 0,
  });
  const skusQuery = useQuery({
    queryKey: ['catalog', 'skus', 'lite'],
    queryFn: () => api.get<Sku[]>('/v1/catalog/skus?limit=500'),
  });
  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
  });

  const skuName = useMemo(() => {
    const m = new Map((skusQuery.data ?? []).map((s) => [s.id, `${s.code} — ${s.name}`]));
    return (sid: string) => m.get(sid) ?? sid;
  }, [skusQuery.data]);
  const customerName = (cid: string) => customersQuery.data?.find((c) => c.id === cid)?.legal_name ?? cid;

  if (id.length === 0) return <ErrorState error={new Error('Missing opportunity id')} />;
  if (oppQuery.isLoading) return <Spinner label="Loading opportunity…" />;
  if (oppQuery.isError) return <ErrorState error={oppQuery.error} />;
  const o = oppQuery.data;
  if (!o) return <EmptyState title="Not found" hint="This opportunity does not exist." />;

  const itemCols: Array<Column<QuoteItem>> = [
    { key: 'sku_id', header: 'SKU', render: (i) => <span className="text-white">{skuName(i.sku_id)}</span> },
    { key: 'quantity', header: 'Qty', render: (i) => i.quantity.toLocaleString('en-US') },
    { key: 'unit_price', header: 'Unit Price', render: (i) => money(i.unit_price) },
    { key: 'discount_pct', header: 'Disc.', render: (i) => `${Number(i.discount_pct)}%` },
    {
      key: 'line', header: 'Line Total',
      render: (i) => <span className="text-cyan">{money(Number(i.quantity) * Number(i.unit_price) * (1 - Number(i.discount_pct) / 100))}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Link to="/sales" className="text-xs text-grape-soft hover:text-cyan">← Sales Pipeline</Link>
        <SectionHeader
          eyebrow="COMMERCIAL · OPPORTUNITY"
          title={`${o.quantity}× ${o.gpu_model}`}
          description={
            <>
              <Link to={`/customers/${o.customer_id}`} className="text-cyan hover:underline">{customerName(o.customer_id)}</Link>
              {o.account_owner ? ` · owner ${o.account_owner}` : ''}
            </>
          }
        />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Stage" value={<Badge tone={STAGE_TONE[o.sales_stage]}>{o.sales_stage}</Badge>} accent="white" />
        <KpiCard label="Probability" value={`${o.probability}%`} accent="cyan" />
        <KpiCard label="Expected MRR" value={money(o.expected_mrr)} accent="cyan" />
        <KpiCard label="Model" value={o.commercial_model} accent="grape" />
        <KpiCard label="Term" value={`${o.duration_months} mo`} accent="white" />
        <KpiCard label="Start" value={o.expected_start ?? '—'} accent="white" />
      </div>

      <section className="flex flex-col gap-4">
        <span className="eyebrow">QUOTES</span>
        {quotesQuery.isLoading ? (
          <Spinner label="Loading quotes…" />
        ) : quotesQuery.isError ? (
          <ErrorState error={quotesQuery.error} />
        ) : (quotesQuery.data ?? []).length === 0 ? (
          <EmptyState title="No quotes" hint="No quotes have been generated for this opportunity." />
        ) : (
          (quotesQuery.data ?? []).map((quote) => (
            <div key={quote.id} className="card flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white">{quote.quote_number}</span>
                  <Badge tone={QUOTE_TONE[quote.status]}>{quote.status}</Badge>
                  <span className="text-xs text-grape-soft">{quote.term_months} mo</span>
                  {quote.valid_until && <span className="text-xs text-grape-soft">· valid until {quote.valid_until}</span>}
                </div>
                <span className="text-sm font-semibold text-cyan">{money(quote.total_amount)}</span>
              </div>
              <DataTable columns={itemCols} rows={quote.items} rowKey={(i) => i.id}
                empty={<EmptyState title="No line items" hint="This quote has no items." />} />
            </div>
          ))
        )}
      </section>
    </div>
  );
}
