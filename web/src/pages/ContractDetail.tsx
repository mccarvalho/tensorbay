// Contract detail / drill-down — plan §22 data model.
// Shows a contract's header plus its items, commitments, price agreements, and
// the reservations booked against it. Read-focused navigability.
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
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

type ContractStatus = 'DRAFT' | 'ACTIVE' | 'AMENDED' | 'RENEWED' | 'TERMINATED' | 'EXPIRED';

interface ContractItem { id: string; sku_id: string; quantity: number; unit_price: string | number; unit: string }
interface Commitment { id: string; type: string; amount: string | number; period: string }
interface PriceAgreement { id: string; sku_id: string; agreed_price: string | number; unit: string }
interface Contract {
  id: string; contract_number: string; customer_id: string; status: ContractStatus;
  term_months: number; start_date: string | null; end_date: string | null; auto_renew: boolean;
  commercial_notes: string | null; document_reference: string | null;
  items: ContractItem[]; commitments: Commitment[]; price_agreements: PriceAgreement[];
}
interface Reservation {
  id: string; gpu_model: string; quantity: number; start_date: string; end_date: string | null; status: string;
}
interface Sku { id: string; code: string; name: string }
interface CustomerLite { id: string; legal_name: string }

const STATUS_TONE: Record<ContractStatus, BadgeTone> = {
  DRAFT: 'neutral', ACTIVE: 'success', AMENDED: 'warning', RENEWED: 'cyan', TERMINATED: 'flamingo', EXPIRED: 'neutral',
};
const RES_TONE: Record<string, BadgeTone> = {
  PENDING: 'warning', ACTIVE: 'success', EXPIRED: 'neutral', RELEASED: 'cyan', CANCELLED: 'flamingo',
};

const money = (v: string | number) =>
  Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });

export default function ContractDetail() {
  const { id = '' } = useParams();

  const contractQuery = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.get<Contract>(`/v1/contracts/${id}`),
    enabled: id.length > 0,
  });
  const reservationsQuery = useQuery({
    queryKey: ['reservations', 'byContract', id],
    queryFn: () => api.get<Reservation[]>(`/v1/reservations?contract_id=${id}&limit=200`),
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

  if (id.length === 0) return <ErrorState error={new Error('Missing contract id')} />;
  if (contractQuery.isLoading) return <Spinner label="Loading contract…" />;
  if (contractQuery.isError) return <ErrorState error={contractQuery.error} />;
  const c = contractQuery.data;
  if (!c) return <EmptyState title="Not found" hint="This contract does not exist." />;

  const itemCols: Array<Column<ContractItem>> = [
    { key: 'sku_id', header: 'SKU', render: (i) => <span className="text-white">{skuName(i.sku_id)}</span> },
    { key: 'quantity', header: 'Qty', render: (i) => i.quantity.toLocaleString('en-US') },
    { key: 'unit', header: 'Unit' },
    { key: 'unit_price', header: 'Unit Price', render: (i) => <span className="text-cyan">{money(i.unit_price)}</span> },
  ];
  const commitCols: Array<Column<Commitment>> = [
    { key: 'type', header: 'Type', render: (x) => <Badge tone="grape">{x.type}</Badge> },
    { key: 'amount', header: 'Amount', render: (x) => money(x.amount) },
    { key: 'period', header: 'Period', render: (x) => <Badge tone="cyan">{x.period}</Badge> },
  ];
  const paCols: Array<Column<PriceAgreement>> = [
    { key: 'sku_id', header: 'SKU', render: (p) => <span className="text-white">{skuName(p.sku_id)}</span> },
    { key: 'agreed_price', header: 'Agreed Price', render: (p) => <span className="text-cyan">{money(p.agreed_price)}</span> },
    { key: 'unit', header: 'Unit' },
  ];
  const resCols: Array<Column<Reservation>> = [
    { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
    { key: 'quantity', header: 'Qty', render: (r) => r.quantity.toLocaleString('en-US') },
    { key: 'start_date', header: 'Start' },
    { key: 'end_date', header: 'End', render: (r) => r.end_date ?? '—' },
    { key: 'status', header: 'Status', render: (r) => <Badge tone={RES_TONE[r.status] ?? 'neutral'}>{r.status}</Badge> },
  ];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Link to="/contracts" className="text-xs text-grape-soft hover:text-cyan">← Contracts</Link>
        <SectionHeader
          eyebrow="COMMERCIAL · CONTRACT"
          title={c.contract_number}
          description={
            <>
              <Link to={`/customers/${c.customer_id}`} className="text-cyan hover:underline">{customerName(c.customer_id)}</Link>
              {c.document_reference ? ` · ref ${c.document_reference}` : ''}
            </>
          }
        />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Status" value={<Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>} accent="white" />
        <KpiCard label="Term" value={`${c.term_months} mo`} accent="cyan" />
        <KpiCard label="Start" value={c.start_date ?? '—'} accent="white" />
        <KpiCard label="Auto-renew" value={c.auto_renew ? 'Yes' : 'No'} accent={c.auto_renew ? 'cyan' : 'white'} />
      </div>

      {c.commercial_notes && (
        <div className="card">
          <span className="eyebrow">NOTES</span>
          <p className="mt-2 text-sm text-grape-soft">{c.commercial_notes}</p>
        </div>
      )}

      <section className="flex flex-col gap-3">
        <span className="eyebrow">LINE ITEMS</span>
        <DataTable columns={itemCols} rows={c.items} rowKey={(i) => i.id}
          empty={<EmptyState title="No items" hint="This contract has no line items." />} />
      </section>

      <section className="flex flex-col gap-3">
        <span className="eyebrow">COMMITMENTS</span>
        <DataTable columns={commitCols} rows={c.commitments} rowKey={(x) => x.id}
          empty={<EmptyState title="No commitments" hint="No spend/quantity commitments on this contract." />} />
      </section>

      <section className="flex flex-col gap-3">
        <span className="eyebrow">PRICE AGREEMENTS</span>
        <DataTable columns={paCols} rows={c.price_agreements} rowKey={(p) => p.id}
          empty={<EmptyState title="No price agreements" hint="No contract-specific pricing." />} />
      </section>

      <section className="flex flex-col gap-3">
        <span className="eyebrow">RESERVATIONS</span>
        {reservationsQuery.isLoading ? (
          <Spinner label="Loading reservations…" />
        ) : reservationsQuery.isError ? (
          <ErrorState error={reservationsQuery.error} />
        ) : (
          <DataTable columns={resCols} rows={reservationsQuery.data ?? []} rowKey={(r) => r.id}
            empty={<EmptyState title="No reservations" hint="No capacity reserved against this contract yet." />} />
        )}
      </section>
    </div>
  );
}
