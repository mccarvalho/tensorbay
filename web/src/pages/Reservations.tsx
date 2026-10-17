// Reservations — list + create (required fields only).
import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
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

type ReservationStatus = 'PENDING' | 'ACTIVE' | 'EXPIRED' | 'RELEASED' | 'CANCELLED';

interface Reservation {
  id: string;
  contract_id: string;
  customer_id: string;
  gpu_model: string;
  quantity: number;
  start_date: string;
  end_date: string | null;
  status: ReservationStatus;
}

interface CustomerLite {
  id: string;
  legal_name: string;
}

interface ContractLite {
  id: string;
  contract_number: string;
  customer_id: string;
}

interface ReservationCreate {
  contract_id: string;
  customer_id: string;
  gpu_model: string;
  quantity: number;
  start_date: string;
}

const STATUS_TONE: Record<ReservationStatus, BadgeTone> = {
  PENDING: 'warning',
  ACTIVE: 'success',
  EXPIRED: 'neutral',
  RELEASED: 'cyan',
  CANCELLED: 'flamingo',
};

const today = (): string => new Date().toISOString().slice(0, 10);

function emptyForm(): ReservationCreate {
  return {
    contract_id: '',
    customer_id: '',
    gpu_model: '',
    quantity: 8,
    start_date: today(),
  };
}

export default function Reservations() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ReservationCreate>(emptyForm);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['reservations'],
    queryFn: () => api.get<Reservation[]>('/v1/reservations?limit=200'),
  });

  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
    enabled: open,
  });

  const contractsQuery = useQuery({
    queryKey: ['contracts', 'lite'],
    queryFn: () => api.get<ContractLite[]>('/v1/contracts?limit=200'),
    enabled: open,
  });

  const createMut = useMutation({
    mutationFn: (payload: ReservationCreate) => api.post<Reservation>('/v1/reservations', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reservations'] });
      setOpen(false);
      setForm(emptyForm());
    },
  });

  const customerName = (id: string): string =>
    customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;
  const contractNumber = (id: string): string =>
    contractsQuery.data?.find((c) => c.id === id)?.contract_number ?? id;

  const columns: Array<Column<Reservation>> = [
    { key: 'gpu_model', header: 'GPU Model', render: (r) => <Badge tone="grape">{r.gpu_model}</Badge> },
    {
      key: 'quantity',
      header: 'Quantity',
      render: (r) => <span className="font-semibold text-white">{r.quantity.toLocaleString('en-US')}</span>,
    },
    { key: 'customer_id', header: 'Customer', render: (r) => customerName(r.customer_id) },
    { key: 'contract_id', header: 'Contract', render: (r) => contractNumber(r.contract_id) },
    { key: 'start_date', header: 'Start' },
    { key: 'end_date', header: 'End', render: (r) => r.end_date ?? '—' },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>,
    },
  ];

  function submit(e: FormEvent) {
    e.preventDefault();
    createMut.mutate(form);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeader
          eyebrow="CAPACITY · COMMITMENTS"
          title="Reservations"
          description="GPU capacity reserved against contracts, ahead of allocation and provisioning."
        />
        <button type="button" className="btn-primary" onClick={() => setOpen(true)}>
          + New Reservation
        </button>
      </div>

      {isLoading ? (
        <Spinner label="Loading reservations…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable
          columns={columns}
          rows={data ?? []}
          rowKey={(r) => r.id}
          empty={<EmptyState title="No reservations yet" hint="Reserve capacity against a contract to hold GPUs." />}
        />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="New Reservation">
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div>
            <label className="label" htmlFor="res_customer">Customer</label>
            <select
              id="res_customer"
              className="input"
              required
              value={form.customer_id}
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            >
              <option value="" disabled>
                {customersQuery.isLoading ? 'Loading…' : 'Select a customer'}
              </option>
              {customersQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.legal_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="res_contract">Contract</label>
            <select
              id="res_contract"
              className="input"
              required
              value={form.contract_id}
              onChange={(e) => setForm({ ...form, contract_id: e.target.value })}
            >
              <option value="" disabled>
                {contractsQuery.isLoading ? 'Loading…' : 'Select a contract'}
              </option>
              {contractsQuery.data
                ?.filter((c) => !form.customer_id || c.customer_id === form.customer_id)
                .map((c) => (
                  <option key={c.id} value={c.id}>{c.contract_number}</option>
                ))}
            </select>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="res_model">GPU Model</label>
              <input
                id="res_model"
                className="input"
                required
                placeholder="H100"
                value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })}
              />
            </div>
            <div>
              <label className="label" htmlFor="res_qty">Quantity</label>
              <input
                id="res_qty"
                type="number"
                min={1}
                className="input"
                required
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label" htmlFor="res_start">Start Date</label>
              <input
                id="res_start"
                type="date"
                className="input"
                required
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </div>
          </div>

          {createMut.isError && <ErrorState error={createMut.error} />}

          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Creating…' : 'Create Reservation'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
