// Inventory — tabbed read-only view across the physical GPU hierarchy:
// regions → datacenters → clusters → racks → servers → gpus.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  type BadgeTone,
  type Column,
} from '../components/ui';

type OperationalStatus = 'ONLINE' | 'OFFLINE' | 'MAINTENANCE' | 'FAILED' | 'DECOMMISSIONED';
type CommercialStatus = 'AVAILABLE' | 'RESERVED' | 'ALLOCATED';

interface Region { id: string; code: string; name: string }
interface Datacenter { id: string; region_id: string; code: string; name: string }
interface Cluster { id: string; datacenter_id: string; code: string; name: string; gpu_model: string }
interface Rack { id: string; cluster_id: string; code: string }
interface Server { id: string; rack_id: string; code: string }
interface Gpu {
  id: string;
  server_id: string;
  gpu_id: string;
  manufacturer: string | null;
  model: string;
  memory_gb: number | null;
  serial_number: string | null;
  operational_status: OperationalStatus;
  commercial_status: CommercialStatus;
}

type TabKey = 'regions' | 'datacenters' | 'clusters' | 'racks' | 'servers' | 'gpus';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'regions', label: 'Regions' },
  { key: 'gpus', label: 'GPUs' },
  { key: 'datacenters', label: 'Datacenters' },
  { key: 'clusters', label: 'Clusters' },
  { key: 'racks', label: 'Racks' },
  { key: 'servers', label: 'Servers' },
];

const OP_TONE: Record<OperationalStatus, BadgeTone> = {
  ONLINE: 'success',
  OFFLINE: 'neutral',
  MAINTENANCE: 'warning',
  FAILED: 'flamingo',
  DECOMMISSIONED: 'neutral',
};

const COMM_TONE: Record<CommercialStatus, BadgeTone> = {
  AVAILABLE: 'cyan',
  RESERVED: 'grape',
  ALLOCATED: 'flamingo',
};

const REGION_COLS: Array<Column<Region>> = [
  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
  { key: 'name', header: 'Name' },
  { key: 'id', header: 'ID', render: (r) => <span className="text-xs text-grape-soft">{r.id}</span> },
];

const DC_COLS: Array<Column<Datacenter>> = [
  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
  { key: 'name', header: 'Name' },
  { key: 'region_id', header: 'Region', render: (r) => <span className="text-xs text-grape-soft">{r.region_id}</span> },
];

const CLUSTER_COLS: Array<Column<Cluster>> = [
  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
  { key: 'name', header: 'Name' },
  { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
  { key: 'datacenter_id', header: 'Datacenter', render: (r) => <span className="text-xs text-grape-soft">{r.datacenter_id}</span> },
];

const RACK_COLS: Array<Column<Rack>> = [
  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
  { key: 'cluster_id', header: 'Cluster', render: (r) => <span className="text-xs text-grape-soft">{r.cluster_id}</span> },
];

const SERVER_COLS: Array<Column<Server>> = [
  { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
  { key: 'rack_id', header: 'Rack', render: (r) => <span className="text-xs text-grape-soft">{r.rack_id}</span> },
];

const GPU_COLS: Array<Column<Gpu>> = [
  { key: 'gpu_id', header: 'GPU ID', render: (r) => <span className="font-medium text-white">{r.gpu_id}</span> },
  { key: 'model', header: 'Model', render: (r) => <Badge tone="grape">{r.model}</Badge> },
  { key: 'manufacturer', header: 'Vendor' },
  { key: 'memory_gb', header: 'Memory', render: (r) => (r.memory_gb ? `${r.memory_gb} GB` : '—') },
  {
    key: 'operational_status',
    header: 'Operational',
    render: (r) => <Badge tone={OP_TONE[r.operational_status]}>{r.operational_status}</Badge>,
  },
  {
    key: 'commercial_status',
    header: 'Commercial',
    render: (r) => <Badge tone={COMM_TONE[r.commercial_status]}>{r.commercial_status}</Badge>,
  },
];

function Tab<Row extends { id: string }>({
  path,
  columns,
  emptyHint,
}: {
  path: string;
  columns: Array<Column<Row>>;
  emptyHint: string;
}) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['inventory', path],
    queryFn: () => api.get<Row[]>(path),
  });

  if (isLoading) return <Spinner label="Loading inventory…" />;
  if (isError) return <ErrorState error={error} />;

  return (
    <DataTable
      columns={columns}
      rows={data ?? []}
      rowKey={(r) => r.id}
      empty={<EmptyState title="Nothing here yet" hint={emptyHint} />}
    />
  );
}

export default function Inventory() {
  const [tab, setTab] = useState<TabKey>('regions');

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        eyebrow="OPERATIONS · PHYSICAL ESTATE"
        title="Inventory"
        description="The physical GPU hierarchy from regions down to individual accelerators."
      />

      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={
              tab === t.key
                ? 'rounded-xl bg-brand-gradient px-4 py-2 text-sm font-semibold text-space-900 shadow-glow'
                : 'rounded-xl border border-white/10 px-4 py-2 text-sm font-medium text-grape-soft transition hover:border-cyan/40 hover:text-white'
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'regions' && (
        <Tab<Region> path="/v1/inventory/regions?limit=200" columns={REGION_COLS} emptyHint="No regions registered." />
      )}
      {tab === 'gpus' && (
        <Tab<Gpu> path="/v1/inventory/gpus?limit=200" columns={GPU_COLS} emptyHint="No GPU assets registered." />
      )}
      {tab === 'datacenters' && (
        <Tab<Datacenter> path="/v1/inventory/datacenters?limit=200" columns={DC_COLS} emptyHint="No datacenters registered." />
      )}
      {tab === 'clusters' && (
        <Tab<Cluster> path="/v1/inventory/clusters?limit=200" columns={CLUSTER_COLS} emptyHint="No clusters registered." />
      )}
      {tab === 'racks' && (
        <Tab<Rack> path="/v1/inventory/racks?limit=200" columns={RACK_COLS} emptyHint="No racks registered." />
      )}
      {tab === 'servers' && (
        <Tab<Server> path="/v1/inventory/servers?limit=200" columns={SERVER_COLS} emptyHint="No servers registered." />
      )}
    </div>
  );
}
