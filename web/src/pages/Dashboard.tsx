// Executive dashboard — mirrors the TensorBay deck's big-stat layout.
// Single call to GET /v1/dashboards/executive returns fleet + capacity +
// commercial + finance rollups.
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import {
  KpiCard,
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  type Column,
} from '../components/ui';

interface FleetSummary {
  installed_gpus: number;
  operational_gpus: number;
  available_gpus: number;
  reserved_gpus: number;
  allocated_gpus: number;
  maintenance_gpus: number;
  offline_gpus: number;
  failed_gpus: number;
  failure_rate_pct: number;
}

interface CapacityRow {
  gpu_model: string;
  physical: number;
  operational: number;
  reserved: number;
  allocated: number;
  available: number;
  incoming: number;
}

interface CommercialSummary {
  contracted_gpus: number;
  reserved_gpus: number;
  active_contracts: number;
  pipeline_gpu_demand: number;
  weighted_pipeline_gpu_demand: number;
  open_opportunities: number;
}

interface FinanceSummary {
  mrr: string;
  arr: string;
  contracted_arr: string;
  revenue_backlog: string;
  weighted_pipeline_mrr: string;
}

interface ExecutiveDashboard {
  fleet: FleetSummary;
  capacity: CapacityRow[];
  commercial: CommercialSummary;
  finance: FinanceSummary;
}

function fmtInt(n: number): string {
  return n.toLocaleString('en-US');
}

function fmtMoney(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

const CAPACITY_COLUMNS: Array<Column<CapacityRow>> = [
  { key: 'gpu_model', header: 'GPU Model', render: (r) => <span className="font-medium text-white">{r.gpu_model}</span> },
  { key: 'physical', header: 'Physical', render: (r) => fmtInt(r.physical) },
  { key: 'operational', header: 'Operational', render: (r) => fmtInt(r.operational) },
  { key: 'reserved', header: 'Reserved', render: (r) => fmtInt(r.reserved) },
  { key: 'allocated', header: 'Allocated', render: (r) => fmtInt(r.allocated) },
  {
    key: 'available',
    header: 'Available',
    render: (r) => <span className="font-semibold text-cyan">{fmtInt(r.available)}</span>,
  },
  {
    key: 'incoming',
    header: 'Incoming',
    render: (r) => (r.incoming > 0 ? <Badge tone="grape">+{fmtInt(r.incoming)}</Badge> : '—'),
  },
];

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['dashboard', 'executive'],
    queryFn: () => api.get<ExecutiveDashboard>('/v1/dashboards/executive'),
  });

  if (isLoading) return <Spinner label="Loading executive overview…" />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <EmptyState title="No data" hint="The executive dashboard returned no payload." />;

  const { fleet, capacity, commercial, finance } = data;

  return (
    <div className="flex flex-col gap-10">
      <SectionHeader
        eyebrow="OVERVIEW · FY2026"
        title="Executive Control Plane"
        description="Real-time rollup of fleet health, capacity, commercial pipeline, and revenue across the NeoCloud GPU estate."
      />

      {/* Finance — headline revenue numbers */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">FINANCE · REVENUE</span>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="MRR" value={fmtMoney(finance.mrr)} accent="cyan" sub="Monthly recurring revenue" />
          <KpiCard label="ARR" value={fmtMoney(finance.arr)} accent="cyan" sub="Annual recurring revenue" />
          <KpiCard label="Contracted ARR" value={fmtMoney(finance.contracted_arr)} accent="grape" sub="Signed contract value" />
          <KpiCard label="Revenue Backlog" value={fmtMoney(finance.revenue_backlog)} accent="grape" sub="Remaining to recognize" />
          <KpiCard label="Weighted Pipeline MRR" value={fmtMoney(finance.weighted_pipeline_mrr)} accent="flamingo" sub="Probability-weighted" />
        </div>
      </section>

      {/* Fleet — GPU health */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">FLEET · GPU HEALTH</span>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
          <KpiCard label="Installed GPUs" value={fmtInt(fleet.installed_gpus)} accent="white" />
          <KpiCard label="Operational" value={fmtInt(fleet.operational_gpus)} accent="cyan" />
          <KpiCard label="Available" value={fmtInt(fleet.available_gpus)} accent="cyan" />
          <KpiCard label="Reserved" value={fmtInt(fleet.reserved_gpus)} accent="grape" />
          <KpiCard label="Allocated" value={fmtInt(fleet.allocated_gpus)} accent="grape" />
          <KpiCard label="Maintenance" value={fmtInt(fleet.maintenance_gpus)} accent="white" />
          <KpiCard label="Offline" value={fmtInt(fleet.offline_gpus)} accent="white" />
          <KpiCard
            label="Failure Rate"
            value={`${fleet.failure_rate_pct.toFixed(1)}%`}
            accent="flamingo"
            sub={`${fmtInt(fleet.failed_gpus)} failed units`}
          />
        </div>
      </section>

      {/* Commercial — pipeline */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">COMMERCIAL · PIPELINE</span>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <KpiCard label="Active Contracts" value={fmtInt(commercial.active_contracts)} accent="cyan" />
          <KpiCard label="Contracted GPUs" value={fmtInt(commercial.contracted_gpus)} accent="grape" />
          <KpiCard label="Reserved GPUs" value={fmtInt(commercial.reserved_gpus)} accent="grape" />
          <KpiCard label="Open Opportunities" value={fmtInt(commercial.open_opportunities)} accent="flamingo" />
          <KpiCard label="Pipeline Demand" value={fmtInt(commercial.pipeline_gpu_demand)} accent="white" sub="GPUs" />
          <KpiCard
            label="Weighted Demand"
            value={fmtInt(Math.round(commercial.weighted_pipeline_gpu_demand))}
            accent="white"
            sub="GPUs (weighted)"
          />
        </div>
      </section>

      {/* Capacity — per-model ledger */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">CAPACITY · BY MODEL</span>
        <DataTable
          columns={CAPACITY_COLUMNS}
          rows={capacity}
          rowKey={(r) => r.gpu_model}
          empty={<EmptyState title="No capacity records" hint="No GPU models are tracked yet." />}
        />
      </section>
    </div>
  );
}
