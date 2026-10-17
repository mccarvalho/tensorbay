// Capacity — per-model ledger lookup, a capacity-check panel, and the
// incoming-capacity pipeline. Both ledger and check require a gpu_model, so a
// model input drives the view.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import {
  SectionHeader,
  KpiCard,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
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

const INCOMING_COLS: Array<Column<IncomingCapacity>> = [
  { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
  { key: 'quantity', header: 'Quantity', render: (r) => r.quantity.toLocaleString('en-US') },
  { key: 'expected_delivery', header: 'Expected Delivery', render: (r) => r.expected_delivery ?? '—' },
  { key: 'expected_operational', header: 'Expected Operational', render: (r) => r.expected_operational ?? '—' },
  { key: 'purchase_order', header: 'PO', render: (r) => r.purchase_order ?? '—' },
];

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

  const incomingQuery = useQuery({
    queryKey: ['capacity', 'incoming'],
    queryFn: () => api.get<IncomingCapacity[]>('/v1/capacity/incoming?limit=200'),
  });

  return (
    <div className="flex flex-col gap-10">
      <SectionHeader
        eyebrow="CAPACITY · GPU LEDGER"
        title="Capacity Planning"
        description="Look up the live capacity ledger per GPU model, run availability checks, and review incoming supply."
      />

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
      <section className="flex flex-col gap-4">
        <span className="eyebrow">SUPPLY · INCOMING</span>
        {incomingQuery.isLoading ? (
          <Spinner label="Loading incoming supply…" />
        ) : incomingQuery.isError ? (
          <ErrorState error={incomingQuery.error} />
        ) : (
          <DataTable
            columns={INCOMING_COLS}
            rows={incomingQuery.data ?? []}
            rowKey={(r) => r.id}
            empty={<EmptyState title="No incoming capacity" hint="No purchase orders are in flight." />}
          />
        )}
      </section>
    </div>
  );
}
