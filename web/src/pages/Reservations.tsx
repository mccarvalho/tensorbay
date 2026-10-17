// Reservations & Allocation workflow — EPIC I / plan §13.
// A Reservation is the commercial commitment; Allocations bind it to physical
// hardware (a cluster + specific GPU assets). Reservation CRUD is gated by
// contract.write; allocation create/edit by allocation.create; release by
// allocation.release.
import { useMemo, useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from '../components/toast';
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
type ReservationStatus = 'PENDING' | 'ACTIVE' | 'EXPIRED' | 'RELEASED' | 'CANCELLED';
type AllocationStatus =
  | 'AVAILABLE' | 'RESERVED' | 'PROVISIONING' | 'ALLOCATED' | 'IN_USE'
  | 'MAINTENANCE' | 'FAILED' | 'RELEASED' | 'DECOMMISSIONED';

const RESERVATION_STATUSES: ReservationStatus[] = ['PENDING', 'ACTIVE', 'EXPIRED', 'RELEASED', 'CANCELLED'];
const ALLOCATION_STATUSES: AllocationStatus[] = [
  'RESERVED', 'PROVISIONING', 'ALLOCATED', 'IN_USE', 'MAINTENANCE', 'FAILED', 'RELEASED', 'DECOMMISSIONED',
];

interface AllocationGpu { id: string; allocation_id: string; gpu_asset_id: string }
interface Allocation {
  id: string; reservation_id: string; status: AllocationStatus;
  cluster_id: string | null; notes: string | null; gpus: AllocationGpu[];
}
interface Reservation {
  id: string; contract_id: string; customer_id: string; gpu_model: string;
  quantity: number; start_date: string; end_date: string | null;
  status: ReservationStatus; allocations: Allocation[];
}
interface CustomerLite { id: string; legal_name: string }
interface ContractLite { id: string; contract_number: string; customer_id: string }
interface ClusterLite { id: string; code: string; name: string; gpu_model: string }
interface GpuLite { id: string; gpu_id: string; model: string; server_id: string; commercial_status: string }

interface ReservationForm {
  contract_id: string; customer_id: string; gpu_model: string;
  quantity: number; start_date: string; end_date: string | null; status: ReservationStatus;
}

const STATUS_TONE: Record<ReservationStatus, BadgeTone> = {
  PENDING: 'warning', ACTIVE: 'success', EXPIRED: 'neutral', RELEASED: 'cyan', CANCELLED: 'flamingo',
};
const ALLOC_TONE: Record<AllocationStatus, BadgeTone> = {
  AVAILABLE: 'cyan', RESERVED: 'grape', PROVISIONING: 'warning', ALLOCATED: 'flamingo',
  IN_USE: 'success', MAINTENANCE: 'warning', FAILED: 'flamingo', RELEASED: 'neutral', DECOMMISSIONED: 'neutral',
};

const today = (): string => new Date().toISOString().slice(0, 10);
const emptyForm = (): ReservationForm => ({
  contract_id: '', customer_id: '', gpu_model: 'H200', quantity: 8,
  start_date: today(), end_date: null, status: 'PENDING',
});

/** GPUs bound across a reservation's live (non-released) allocations. */
function allocatedCount(r: Reservation): number {
  return r.allocations
    .filter((a) => a.status !== 'RELEASED' && a.status !== 'DECOMMISSIONED')
    .reduce((n, a) => n + a.gpus.length, 0);
}

// --------------------------------------------------------------------------- //
export default function Reservations() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWriteRes = hasPermission('contract.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ReservationForm>(emptyForm);
  const [manageFor, setManageFor] = useState<Reservation | null>(null);

  const reservationsQuery = useQuery({
    queryKey: ['reservations'],
    queryFn: () => api.get<Reservation[]>('/v1/reservations?limit=200'),
  });
  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
  });
  const contractsQuery = useQuery({
    queryKey: ['contracts', 'lite'],
    queryFn: () => api.get<ContractLite[]>('/v1/contracts?limit=200'),
  });

  const customerName = (id: string) => customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;
  const contractNumber = (id: string) => contractsQuery.data?.find((c) => c.id === id)?.contract_number ?? id;

  const reset = () => { setEditId(null); setForm(emptyForm()); };
  const save = useMutation({
    mutationFn: () => {
      if (editId) {
        // Reservation PATCH only accepts a subset (no contract/customer change).
        const payload = {
          gpu_model: form.gpu_model, quantity: form.quantity,
          start_date: form.start_date, end_date: form.end_date, status: form.status,
        };
        return api.patch<Reservation>(`/v1/reservations/${editId}`, payload);
      }
      return api.post<Reservation>('/v1/reservations', form);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reservations'] }); toast.success(editId ? 'Reservation updated' : 'Reservation created'); setOpen(false); reset(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save reservation')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/reservations/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['reservations'] }); toast.success('Reservation deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete reservation')),
  });

  function openEdit(r: Reservation) {
    setEditId(r.id);
    setForm({
      contract_id: r.contract_id, customer_id: r.customer_id, gpu_model: r.gpu_model,
      quantity: r.quantity, start_date: r.start_date, end_date: r.end_date, status: r.status,
    });
    setOpen(true);
  }

  // Keep the "Manage Allocations" modal data fresh after mutations.
  const liveManageFor = useMemo(
    () => (manageFor ? reservationsQuery.data?.find((r) => r.id === manageFor.id) ?? manageFor : null),
    [manageFor, reservationsQuery.data],
  );

  const columns: Array<Column<Reservation>> = [
    { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
    {
      key: 'quantity', header: 'Allocated / Reserved',
      render: (r) => {
        const alloc = allocatedCount(r);
        const pct = r.quantity > 0 ? Math.min(100, (alloc / r.quantity) * 100) : 0;
        return (
          <div className="flex flex-col gap-1">
            <span className="text-sm font-semibold text-white">{alloc.toLocaleString('en-US')} / {r.quantity.toLocaleString('en-US')}</span>
            <div className="h-1.5 w-28 overflow-hidden rounded bg-white/10">
              <div className="h-full bg-cyan" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      },
    },
    { key: 'customer_id', header: 'Customer', render: (r) => customerName(r.customer_id) },
    { key: 'contract_id', header: 'Contract', render: (r) => contractNumber(r.contract_id) },
    { key: 'start_date', header: 'Start' },
    { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (r) => (
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setManageFor(r)}>
            Allocations ({r.allocations.length})
          </button>
          {canWriteRes && (
            <>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(r)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete reservation of ${r.quantity}× ${r.gpu_model}?`)) del.mutate(r.id); }}>Delete</button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeader
          eyebrow="CAPACITY · COMMITMENTS"
          title="Reservations &amp; Allocations"
          description="GPU capacity reserved against contracts, then allocated to physical clusters and specific GPUs."
        />
        {canWriteRes && (
          <button type="button" className="btn-primary" onClick={() => { reset(); setOpen(true); }}>+ New Reservation</button>
        )}
      </div>

      {del.isError && <ErrorState error={del.error} />}
      {reservationsQuery.isLoading ? (
        <Spinner label="Loading reservations…" />
      ) : reservationsQuery.isError ? (
        <ErrorState error={reservationsQuery.error} />
      ) : (
        <DataTable columns={columns} rows={reservationsQuery.data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No reservations yet" hint="Reserve capacity against a contract to hold GPUs." />} />
      )}

      {/* Reservation create/edit */}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Reservation' : 'New Reservation'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          {!editId && (
            <>
              <div>
                <label className="label" htmlFor="res_customer">Customer</label>
                <select id="res_customer" className="input" required value={form.customer_id}
                  onChange={(e) => setForm({ ...form, customer_id: e.target.value, contract_id: '' })}>
                  <option value="" disabled>{customersQuery.isLoading ? 'Loading…' : 'Select a customer'}</option>
                  {customersQuery.data?.map((c) => <option key={c.id} value={c.id}>{c.legal_name}</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="res_contract">Contract</label>
                <select id="res_contract" className="input" required value={form.contract_id}
                  onChange={(e) => setForm({ ...form, contract_id: e.target.value })}>
                  <option value="" disabled>{contractsQuery.isLoading ? 'Loading…' : 'Select a contract'}</option>
                  {contractsQuery.data?.filter((c) => !form.customer_id || c.customer_id === form.customer_id)
                    .map((c) => <option key={c.id} value={c.id}>{c.contract_number}</option>)}
                </select>
              </div>
            </>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="res_model">GPU Model</label>
              <input id="res_model" className="input" required list="res-gpu-models" value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })} />
              <datalist id="res-gpu-models">{GPU_MODELS.map((m) => <option key={m} value={m} />)}</datalist>
            </div>
            <div>
              <label className="label" htmlFor="res_qty">Quantity</label>
              <input id="res_qty" type="number" min={1} className="input" required value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label" htmlFor="res_start">Start Date</label>
              <input id="res_start" type="date" className="input" required value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </div>
          </div>
          {editId && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label" htmlFor="res_end">End Date</label>
                <input id="res_end" type="date" className="input" value={form.end_date ?? ''}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value || null })} />
              </div>
              <div>
                <label className="label" htmlFor="res_status">Status</label>
                <select id="res_status" className="input" value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value as ReservationStatus })}>
                  {RESERVATION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
          )}
          {save.isError && <ErrorState error={save.error} />}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Reservation'}
            </button>
          </div>
        </form>
      </Modal>

      {liveManageFor && (
        <AllocationsModal reservation={liveManageFor} onClose={() => setManageFor(null)}
          onChanged={() => qc.invalidateQueries({ queryKey: ['reservations'] })} />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Allocations manager
// --------------------------------------------------------------------------- //
function AllocationsModal({ reservation, onClose, onChanged }: {
  reservation: Reservation; onClose: () => void; onChanged: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const canCreate = hasPermission('allocation.create');
  const canRelease = hasPermission('allocation.release');
  const base = `/v1/reservations/${reservation.id}/allocations`;

  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [clusterId, setClusterId] = useState('');
  const [status, setStatus] = useState<AllocationStatus>('RESERVED');
  const [notes, setNotes] = useState('');
  const [selectedGpus, setSelectedGpus] = useState<string[]>([]);

  // Clusters for this reservation's GPU model; GPUs available for binding.
  const clustersQuery = useQuery({
    queryKey: ['inventory', 'clusters', 'lite'],
    queryFn: () => api.get<ClusterLite[]>('/v1/inventory/clusters?limit=500'),
  });
  const gpusQuery = useQuery({
    queryKey: ['inventory', 'gpus', 'available', reservation.gpu_model],
    queryFn: () => api.get<GpuLite[]>(
      `/v1/inventory/gpus?gpu_model=${encodeURIComponent(reservation.gpu_model)}&commercial_status=AVAILABLE&limit=500`,
    ),
  });

  const clusterCode = (id: string | null) =>
    id ? clustersQuery.data?.find((c) => c.id === id)?.code ?? id : '—';

  const refresh = () => { qc.invalidateQueries({ queryKey: ['reservations'] }); onChanged(); };
  const resetForm = () => { setEditId(null); setClusterId(''); setStatus('RESERVED'); setNotes(''); setSelectedGpus([]); };

  const save = useMutation({
    mutationFn: () => {
      if (editId) {
        return api.patch<Allocation>(`${base}/${editId}`, {
          status, cluster_id: clusterId || null, notes: notes || null,
        });
      }
      return api.post<Allocation>(base, {
        status, cluster_id: clusterId || null, notes: notes || null, gpu_asset_ids: selectedGpus,
      });
    },
    onSuccess: () => { refresh(); toast.success(editId ? 'Allocation updated' : 'Allocation created'); setShowForm(false); resetForm(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save allocation')),
  });
  const release = useMutation({
    mutationFn: (id: string) => api.post<Allocation>(`${base}/${id}/release`, {}),
    onSuccess: () => { refresh(); toast.success('Allocation released'); },
    onError: (e) => toast.error(errMessage(e, 'Could not release allocation')),
  });

  function openEdit(a: Allocation) {
    setEditId(a.id); setClusterId(a.cluster_id ?? ''); setStatus(a.status); setNotes(a.notes ?? '');
    setSelectedGpus([]); setShowForm(true);
  }

  const toggleGpu = (id: string) =>
    setSelectedGpus((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const alloc = allocatedCount(reservation);
  // Clusters narrowed to the reservation's model (fall back to all if none match).
  const modelClusters = (clustersQuery.data ?? []).filter((c) => c.gpu_model === reservation.gpu_model);
  const clusterOptions = modelClusters.length > 0 ? modelClusters : (clustersQuery.data ?? []);

  return (
    <Modal open onClose={onClose} title={`Allocations · ${reservation.quantity}× ${reservation.gpu_model}`}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-grape-soft">
            {alloc.toLocaleString('en-US')} of {reservation.quantity.toLocaleString('en-US')} GPUs allocated
          </span>
          {canCreate && !showForm && (
            <button type="button" className="btn-primary px-3 py-1.5 text-sm"
              onClick={() => { resetForm(); setShowForm(true); }}>+ Allocate</button>
          )}
        </div>

        {/* Existing allocations */}
        {reservation.allocations.length === 0 ? (
          <EmptyState title="No allocations yet" hint="Bind this reservation to a cluster and specific GPUs." />
        ) : (
          <div className="flex flex-col gap-2">
            {reservation.allocations.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2">
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <Badge tone={ALLOC_TONE[a.status]}>{a.status}</Badge>
                    <span className="text-sm text-white">{clusterCode(a.cluster_id)}</span>
                    <span className="text-xs text-grape-soft">{a.gpus.length} GPU{a.gpus.length === 1 ? '' : 's'}</span>
                  </div>
                  {a.notes && <span className="text-xs text-grape-soft">{a.notes}</span>}
                </div>
                <div className="flex gap-2">
                  {canCreate && a.status !== 'RELEASED' && (
                    <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(a)}>Edit</button>
                  )}
                  {canRelease && a.status !== 'RELEASED' && (
                    <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                      onClick={() => { if (confirm('Release this allocation?')) release.mutate(a.id); }}>Release</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {release.isError && <ErrorState error={release.error} />}

        {/* Allocate / edit form */}
        {showForm && (
          <form className="flex flex-col gap-4 border-t border-white/10 pt-4"
            onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
            <h4 className="text-sm font-semibold text-white">{editId ? 'Edit Allocation' : 'New Allocation'}</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label" htmlFor="alloc_cluster">Cluster</label>
                <select id="alloc_cluster" className="input" value={clusterId}
                  onChange={(e) => setClusterId(e.target.value)}>
                  <option value="">{clustersQuery.isLoading ? 'Loading…' : '— none —'}</option>
                  {clusterOptions.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="alloc_status">Status</label>
                <select id="alloc_status" className="input" value={status}
                  onChange={(e) => setStatus(e.target.value as AllocationStatus)}>
                  {ALLOCATION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="label" htmlFor="alloc_notes">Notes</label>
              <input id="alloc_notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
            {!editId && (
              <div>
                <label className="label">
                  Specific GPUs ({reservation.gpu_model}, available){selectedGpus.length ? ` · ${selectedGpus.length} selected` : ''}
                </label>
                <div className="max-h-40 overflow-auto rounded-xl border border-white/10 p-2">
                  {gpusQuery.isLoading ? (
                    <span className="text-xs text-grape-soft">Loading GPUs…</span>
                  ) : (gpusQuery.data ?? []).length === 0 ? (
                    <span className="text-xs text-grape-soft">No AVAILABLE {reservation.gpu_model} GPUs in inventory. You can still allocate at the cluster level.</span>
                  ) : (
                    (gpusQuery.data ?? []).map((g) => (
                      <label key={g.id} className="flex cursor-pointer items-center gap-2 py-0.5 text-sm text-white">
                        <input type="checkbox" checked={selectedGpus.includes(g.id)} onChange={() => toggleGpu(g.id)} />
                        <span>{g.gpu_id}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            )}
            {save.isError && <ErrorState error={save.error} />}
            <div className="flex justify-end gap-3">
              <button type="button" className="btn-ghost" onClick={() => { setShowForm(false); resetForm(); }}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={save.isPending}>
                {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Allocate'}
              </button>
            </div>
          </form>
        )}

        {!showForm && (
          <div className="flex justify-end">
            <button type="button" className="btn-ghost" onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </Modal>
  );
}
