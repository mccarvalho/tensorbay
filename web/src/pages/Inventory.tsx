// Inventory — full CRUD across the physical GPU hierarchy:
// regions → datacenters → clusters → racks → servers → GPUs.
// Writes gated by inventory.write; parent pickers resolve parent names.
import { useMemo, useState, cloneElement, isValidElement, type FormEvent, type ReactNode, type ReactElement } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { GPU_MODELS } from '../constants';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  type BadgeTone,
  type Column,
} from '../components/ui';

// --------------------------------------------------------------------------- //
type OperationalStatus = 'ONLINE' | 'OFFLINE' | 'MAINTENANCE' | 'FAILED' | 'DECOMMISSIONED';
type CommercialStatus = 'AVAILABLE' | 'RESERVED' | 'ALLOCATED';
const OPERATIONAL_STATUSES: OperationalStatus[] = ['ONLINE', 'OFFLINE', 'MAINTENANCE', 'FAILED', 'DECOMMISSIONED'];
const COMMERCIAL_STATUSES: CommercialStatus[] = ['AVAILABLE', 'RESERVED', 'ALLOCATED'];

interface Region { id: string; code: string; name: string }
interface Datacenter { id: string; region_id: string; code: string; name: string }
interface Cluster { id: string; datacenter_id: string; code: string; name: string; gpu_model: string }
interface Rack { id: string; cluster_id: string; code: string }
interface Server { id: string; rack_id: string; code: string }
interface Gpu {
  id: string; server_id: string; gpu_id: string; manufacturer: string | null; model: string;
  memory_gb: number | null; serial_number: string | null; acquisition_cost: string | number | null;
  acquisition_date: string | null; supplier: string | null; warranty: string | null;
  operational_status: OperationalStatus; commercial_status: CommercialStatus;
}

const OP_TONE: Record<OperationalStatus, BadgeTone> = {
  ONLINE: 'success', OFFLINE: 'neutral', MAINTENANCE: 'warning', FAILED: 'flamingo', DECOMMISSIONED: 'neutral',
};
const COMM_TONE: Record<CommercialStatus, BadgeTone> = {
  AVAILABLE: 'cyan', RESERVED: 'grape', ALLOCATED: 'flamingo',
};

type TabKey = 'regions' | 'datacenters' | 'clusters' | 'racks' | 'servers' | 'gpus';
const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'regions', label: 'Regions' },
  { key: 'datacenters', label: 'Datacenters' },
  { key: 'clusters', label: 'Clusters' },
  { key: 'racks', label: 'Racks' },
  { key: 'servers', label: 'Servers' },
  { key: 'gpus', label: 'GPUs' },
];

const q = (p: string) => `/v1/inventory/${p}?limit=500`;

// --------------------------------------------------------------------------- //
export default function Inventory() {
  const [tab, setTab] = useState<TabKey>('regions');
  const canWrite = hasPermission('inventory.write');

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        eyebrow="OPERATIONS · PHYSICAL ESTATE"
        title="Inventory"
        description="The physical GPU hierarchy from regions down to individual accelerators — full lifecycle management."
      />
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={tab === t.key
              ? 'rounded-xl bg-brand-gradient px-4 py-2 text-sm font-semibold text-space-900 shadow-glow'
              : 'rounded-xl border border-white/10 px-4 py-2 text-sm font-medium text-grape-soft transition hover:border-cyan/40 hover:text-white'}>
            {t.label}
          </button>
        ))}
      </div>
      {!canWrite && (
        <p className="text-xs text-grape-soft">Read-only access. Operations roles can add and edit inventory.</p>
      )}
      {tab === 'regions' && <RegionsTab canWrite={canWrite} />}
      {tab === 'datacenters' && <DatacentersTab canWrite={canWrite} />}
      {tab === 'clusters' && <ClustersTab canWrite={canWrite} />}
      {tab === 'racks' && <RacksTab canWrite={canWrite} />}
      {tab === 'servers' && <ServersTab canWrite={canWrite} />}
      {tab === 'gpus' && <GpusTab canWrite={canWrite} />}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Generic helpers
// --------------------------------------------------------------------------- //
function useList<T>(key: string) {
  return useQuery({ queryKey: ['inventory', key], queryFn: () => api.get<T[]>(q(key)) });
}

function ActionCell({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={onEdit}>Edit</button>
      <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo" onClick={onDelete}>Delete</button>
    </div>
  );
}

function Toolbar({ canWrite, onNew, label }: { canWrite: boolean; onNew: () => void; label: string }) {
  if (!canWrite) return null;
  return (
    <div className="flex justify-end">
      <button type="button" className="btn-primary" onClick={onNew}>+ New {label}</button>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  const id = `fld-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  return (
    <div>
      <label className="label" htmlFor={id}>{label}</label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<{ id?: string }>, { id })
        : children}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Regions
// --------------------------------------------------------------------------- //
function RegionsTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Region>('regions');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ code: '', name: '' });

  const reset = () => { setEditId(null); setForm({ code: '', name: '' }); };
  const save = useMutation({
    mutationFn: () => editId
      ? api.patch<Region>(`/v1/inventory/regions/${editId}`, form)
      : api.post<Region>('/v1/inventory/regions', form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'regions'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/regions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'regions'] }),
  });

  const cols: Array<Column<Region>> = [
    { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
    { key: 'name', header: 'Name' },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Region) => (
      <ActionCell onEdit={() => { setEditId(r.id); setForm({ code: r.code, name: r.name }); setOpen(true); }}
        onDelete={() => { if (confirm(`Delete region ${r.code}?`)) del.mutate(r.id); }} />) } as Column<Region>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="Region" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No regions" hint="Add a region (e.g. us-east) to start the hierarchy." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Region' : 'New Region'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Code"><input className="input" required placeholder="us-east" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          <Field label="Name"><input className="input" required placeholder="US East" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="Region" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Datacenters (parent: region)
// --------------------------------------------------------------------------- //
function DatacentersTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Datacenter>('datacenters');
  const regions = useList<Region>('regions');
  const regionName = useMemo(() => {
    const m = new Map((regions.data ?? []).map((r) => [r.id, r.code]));
    return (id: string) => m.get(id) ?? id;
  }, [regions.data]);

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ region_id: '', code: '', name: '' });
  const reset = () => { setEditId(null); setForm({ region_id: '', code: '', name: '' }); };

  const save = useMutation({
    mutationFn: () => editId
      ? api.patch<Datacenter>(`/v1/inventory/datacenters/${editId}`, form)
      : api.post<Datacenter>('/v1/inventory/datacenters', form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'datacenters'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/datacenters/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'datacenters'] }),
  });

  const cols: Array<Column<Datacenter>> = [
    { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
    { key: 'name', header: 'Name' },
    { key: 'region_id', header: 'Region', render: (r) => <Badge tone="cyan">{regionName(r.region_id)}</Badge> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Datacenter) => (
      <ActionCell onEdit={() => { setEditId(r.id); setForm({ region_id: r.region_id, code: r.code, name: r.name }); setOpen(true); }}
        onDelete={() => { if (confirm(`Delete datacenter ${r.code}?`)) del.mutate(r.id); }} />) } as Column<Datacenter>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="Datacenter" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No datacenters" hint="Add a datacenter under a region." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Datacenter' : 'New Datacenter'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Region">
            <select className="input" required value={form.region_id} onChange={(e) => setForm({ ...form, region_id: e.target.value })}>
              <option value="" disabled>{regions.isLoading ? 'Loading…' : 'Select region'}</option>
              {regions.data?.map((r) => <option key={r.id} value={r.id}>{r.code} — {r.name}</option>)}
            </select>
          </Field>
          <Field label="Code"><input className="input" required placeholder="DC-MIA-01" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          <Field label="Name"><input className="input" required placeholder="Miami 01" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="Datacenter" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Clusters (parent: datacenter; has gpu_model)
// --------------------------------------------------------------------------- //
function ClustersTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Cluster>('clusters');
  const dcs = useList<Datacenter>('datacenters');
  const dcName = useMemo(() => {
    const m = new Map((dcs.data ?? []).map((d) => [d.id, d.code]));
    return (id: string) => m.get(id) ?? id;
  }, [dcs.data]);

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ datacenter_id: '', code: '', name: '', gpu_model: 'H200' });
  const reset = () => { setEditId(null); setForm({ datacenter_id: '', code: '', name: '', gpu_model: 'H200' }); };

  const save = useMutation({
    mutationFn: () => editId
      ? api.patch<Cluster>(`/v1/inventory/clusters/${editId}`, form)
      : api.post<Cluster>('/v1/inventory/clusters', form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'clusters'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/clusters/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'clusters'] }),
  });

  const cols: Array<Column<Cluster>> = [
    { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
    { key: 'name', header: 'Name' },
    { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
    { key: 'datacenter_id', header: 'Datacenter', render: (r) => <Badge tone="cyan">{dcName(r.datacenter_id)}</Badge> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Cluster) => (
      <ActionCell onEdit={() => { setEditId(r.id); setForm({ datacenter_id: r.datacenter_id, code: r.code, name: r.name, gpu_model: r.gpu_model }); setOpen(true); }}
        onDelete={() => { if (confirm(`Delete cluster ${r.code}?`)) del.mutate(r.id); }} />) } as Column<Cluster>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="Cluster" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No clusters" hint="Add a GPU cluster under a datacenter." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Cluster' : 'New Cluster'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Datacenter">
            <select className="input" required value={form.datacenter_id} onChange={(e) => setForm({ ...form, datacenter_id: e.target.value })}>
              <option value="" disabled>{dcs.isLoading ? 'Loading…' : 'Select datacenter'}</option>
              {dcs.data?.map((d) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Code"><input className="input" required placeholder="H200-CLUSTER-01" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
            <Field label="GPU Model">
              <input id="fld-gpu-model" className="input" required list="cluster-gpu" value={form.gpu_model} onChange={(e) => setForm({ ...form, gpu_model: e.target.value })} />
              <datalist id="cluster-gpu">{GPU_MODELS.map((m) => <option key={m} value={m} />)}</datalist>
            </Field>
          </div>
          <Field label="Name"><input className="input" required placeholder="H200 Cluster 01" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="Cluster" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Racks (parent: cluster)
// --------------------------------------------------------------------------- //
function RacksTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Rack>('racks');
  const clusters = useList<Cluster>('clusters');
  const clusterName = useMemo(() => {
    const m = new Map((clusters.data ?? []).map((c) => [c.id, c.code]));
    return (id: string) => m.get(id) ?? id;
  }, [clusters.data]);

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ cluster_id: '', code: '' });
  const reset = () => { setEditId(null); setForm({ cluster_id: '', code: '' }); };

  const save = useMutation({
    mutationFn: () => editId
      ? api.patch<Rack>(`/v1/inventory/racks/${editId}`, form)
      : api.post<Rack>('/v1/inventory/racks', form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'racks'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/racks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'racks'] }),
  });

  const cols: Array<Column<Rack>> = [
    { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
    { key: 'cluster_id', header: 'Cluster', render: (r) => <Badge tone="grape">{clusterName(r.cluster_id)}</Badge> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Rack) => (
      <ActionCell onEdit={() => { setEditId(r.id); setForm({ cluster_id: r.cluster_id, code: r.code }); setOpen(true); }}
        onDelete={() => { if (confirm(`Delete rack ${r.code}?`)) del.mutate(r.id); }} />) } as Column<Rack>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="Rack" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No racks" hint="Add a rack under a cluster." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Rack' : 'New Rack'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Cluster">
            <select className="input" required value={form.cluster_id} onChange={(e) => setForm({ ...form, cluster_id: e.target.value })}>
              <option value="" disabled>{clusters.isLoading ? 'Loading…' : 'Select cluster'}</option>
              {clusters.data?.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
            </select>
          </Field>
          <Field label="Code"><input className="input" required placeholder="RACK-21" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="Rack" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Servers (parent: rack)
// --------------------------------------------------------------------------- //
function ServersTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Server>('servers');
  const racks = useList<Rack>('racks');
  const rackName = useMemo(() => {
    const m = new Map((racks.data ?? []).map((r) => [r.id, r.code]));
    return (id: string) => m.get(id) ?? id;
  }, [racks.data]);

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ rack_id: '', code: '' });
  const reset = () => { setEditId(null); setForm({ rack_id: '', code: '' }); };

  const save = useMutation({
    mutationFn: () => editId
      ? api.patch<Server>(`/v1/inventory/servers/${editId}`, form)
      : api.post<Server>('/v1/inventory/servers', form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'servers'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/servers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'servers'] }),
  });

  const cols: Array<Column<Server>> = [
    { key: 'code', header: 'Code', render: (r) => <span className="font-medium text-white">{r.code}</span> },
    { key: 'rack_id', header: 'Rack', render: (r) => <Badge tone="grape">{rackName(r.rack_id)}</Badge> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Server) => (
      <ActionCell onEdit={() => { setEditId(r.id); setForm({ rack_id: r.rack_id, code: r.code }); setOpen(true); }}
        onDelete={() => { if (confirm(`Delete server ${r.code}?`)) del.mutate(r.id); }} />) } as Column<Server>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="Server" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No servers" hint="Add a server under a rack." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Server' : 'New Server'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Rack">
            <select className="input" required value={form.rack_id} onChange={(e) => setForm({ ...form, rack_id: e.target.value })}>
              <option value="" disabled>{racks.isLoading ? 'Loading…' : 'Select rack'}</option>
              {racks.data?.map((r) => <option key={r.id} value={r.id}>{r.code}</option>)}
            </select>
          </Field>
          <Field label="Code"><input className="input" required placeholder="SRV-0042" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="Server" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// GPUs (parent: server; full asset fields + status)
// --------------------------------------------------------------------------- //
interface GpuForm {
  server_id: string; gpu_id: string; manufacturer: string; model: string; memory_gb: string;
  serial_number: string; acquisition_cost: string; acquisition_date: string; supplier: string;
  warranty: string; operational_status: OperationalStatus; commercial_status: CommercialStatus;
}
const emptyGpu = (): GpuForm => ({
  server_id: '', gpu_id: '', manufacturer: 'NVIDIA', model: 'H200', memory_gb: '', serial_number: '',
  acquisition_cost: '', acquisition_date: '', supplier: '', warranty: '',
  operational_status: 'ONLINE', commercial_status: 'AVAILABLE',
});

function GpusTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const list = useList<Gpu>('gpus');
  const servers = useList<Server>('servers');
  const serverName = useMemo(() => {
    const m = new Map((servers.data ?? []).map((s) => [s.id, s.code]));
    return (id: string) => m.get(id) ?? id;
  }, [servers.data]);

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<GpuForm>(emptyGpu);
  const reset = () => { setEditId(null); setForm(emptyGpu()); };

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        server_id: form.server_id,
        gpu_id: form.gpu_id,
        manufacturer: form.manufacturer || null,
        model: form.model,
        memory_gb: form.memory_gb ? Number(form.memory_gb) : null,
        serial_number: form.serial_number || null,
        acquisition_cost: form.acquisition_cost ? Number(form.acquisition_cost) : null,
        acquisition_date: form.acquisition_date || null,
        supplier: form.supplier || null,
        warranty: form.warranty || null,
        operational_status: form.operational_status,
        commercial_status: form.commercial_status,
      };
      return editId
        ? api.patch<Gpu>(`/v1/inventory/gpus/${editId}`, payload)
        : api.post<Gpu>('/v1/inventory/gpus', payload);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inventory', 'gpus'] }); setOpen(false); reset(); },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/inventory/gpus/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', 'gpus'] }),
  });

  function openEdit(g: Gpu) {
    setEditId(g.id);
    setForm({
      server_id: g.server_id, gpu_id: g.gpu_id, manufacturer: g.manufacturer ?? '', model: g.model,
      memory_gb: g.memory_gb != null ? String(g.memory_gb) : '', serial_number: g.serial_number ?? '',
      acquisition_cost: g.acquisition_cost != null ? String(g.acquisition_cost) : '',
      acquisition_date: g.acquisition_date ?? '', supplier: g.supplier ?? '', warranty: g.warranty ?? '',
      operational_status: g.operational_status, commercial_status: g.commercial_status,
    });
    setOpen(true);
  }

  const cols: Array<Column<Gpu>> = [
    { key: 'gpu_id', header: 'GPU ID', render: (r) => <span className="font-medium text-white">{r.gpu_id}</span> },
    { key: 'model', header: 'Model', render: (r) => <Badge tone="grape">{r.model}</Badge> },
    { key: 'memory_gb', header: 'Memory', render: (r) => (r.memory_gb ? `${r.memory_gb} GB` : '—') },
    { key: 'server_id', header: 'Server', render: (r) => <span className="text-xs text-grape-soft">{serverName(r.server_id)}</span> },
    { key: 'operational_status', header: 'Operational', render: (r) => <Badge tone={OP_TONE[r.operational_status]}>{r.operational_status}</Badge> },
    { key: 'commercial_status', header: 'Commercial', render: (r) => <Badge tone={COMM_TONE[r.commercial_status]}>{r.commercial_status}</Badge> },
    ...(canWrite ? [{ key: 'a', header: '', className: 'text-right', render: (r: Gpu) => (
      <ActionCell onEdit={() => openEdit(r)} onDelete={() => { if (confirm(`Delete GPU ${r.gpu_id}?`)) del.mutate(r.id); }} />) } as Column<Gpu>] : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      <Toolbar canWrite={canWrite} onNew={() => { reset(); setOpen(true); }} label="GPU" />
      {del.isError && <ErrorState error={del.error} />}
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={cols} rows={list.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No GPU assets" hint="Register GPUs under a server to track the fleet." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit GPU Asset' : 'New GPU Asset'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Server">
            <select className="input" required value={form.server_id} onChange={(e) => setForm({ ...form, server_id: e.target.value })}>
              <option value="" disabled>{servers.isLoading ? 'Loading…' : 'Select server'}</option>
              {servers.data?.map((s) => <option key={s.id} value={s.id}>{s.code}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="GPU ID"><input className="input" required placeholder="GPU-US-FL-000342" value={form.gpu_id} onChange={(e) => setForm({ ...form, gpu_id: e.target.value })} /></Field>
            <Field label="Model">
              <input id="fld-model" className="input" required list="gpu-model-opts" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              <datalist id="gpu-model-opts">{GPU_MODELS.map((m) => <option key={m} value={m} />)}</datalist>
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Manufacturer"><input className="input" value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })} /></Field>
            <Field label="Memory (GB)"><input type="number" min={0} className="input" value={form.memory_gb} onChange={(e) => setForm({ ...form, memory_gb: e.target.value })} /></Field>
            <Field label="Serial Number"><input className="input" value={form.serial_number} onChange={(e) => setForm({ ...form, serial_number: e.target.value })} /></Field>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Acquisition Cost (USD)"><input type="number" min={0} step="0.01" className="input" value={form.acquisition_cost} onChange={(e) => setForm({ ...form, acquisition_cost: e.target.value })} /></Field>
            <Field label="Acquisition Date"><input type="date" className="input" value={form.acquisition_date} onChange={(e) => setForm({ ...form, acquisition_date: e.target.value })} /></Field>
            <Field label="Supplier"><input className="input" value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} /></Field>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Warranty"><input className="input" placeholder="3 years" value={form.warranty} onChange={(e) => setForm({ ...form, warranty: e.target.value })} /></Field>
            <Field label="Operational Status">
              <select className="input" value={form.operational_status} onChange={(e) => setForm({ ...form, operational_status: e.target.value as OperationalStatus })}>
                {OPERATIONAL_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Commercial Status">
              <select className="input" value={form.commercial_status} onChange={(e) => setForm({ ...form, commercial_status: e.target.value as CommercialStatus })}>
                {COMMERCIAL_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
          </div>
          {save.isError && <ErrorState error={save.error} />}
          <ModalFooter editId={editId} pending={save.isPending} onCancel={() => { setOpen(false); reset(); }} noun="GPU" />
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ModalFooter({ editId, pending, onCancel, noun }: { editId: string | null; pending: boolean; onCancel: () => void; noun: string }) {
  return (
    <div className="mt-2 flex justify-end gap-3">
      <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
      <button type="submit" className="btn-primary" disabled={pending}>
        {pending ? 'Saving…' : editId ? 'Save Changes' : `Create ${noun}`}
      </button>
    </div>
  );
}
