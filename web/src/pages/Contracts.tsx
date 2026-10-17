// Contracts — list + create (required fields only).
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

type ContractStatus = 'DRAFT' | 'ACTIVE' | 'AMENDED' | 'RENEWED' | 'TERMINATED' | 'EXPIRED';

interface Contract {
  id: string;
  contract_number: string;
  customer_id: string;
  status: ContractStatus;
  term_months: number;
  start_date: string | null;
  end_date: string | null;
  auto_renew: boolean;
  created_at: string;
}

interface CustomerLite {
  id: string;
  legal_name: string;
}

interface ContractCreate {
  contract_number: string;
  customer_id: string;
  term_months: number;
}

const STATUS_TONE: Record<ContractStatus, BadgeTone> = {
  DRAFT: 'neutral',
  ACTIVE: 'success',
  AMENDED: 'cyan',
  RENEWED: 'cyan',
  TERMINATED: 'flamingo',
  EXPIRED: 'warning',
};

const EMPTY_FORM: ContractCreate = {
  contract_number: '',
  customer_id: '',
  term_months: 12,
};

export default function Contracts() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ContractCreate>(EMPTY_FORM);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api.get<Contract[]>('/v1/contracts?limit=200'),
  });

  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
    enabled: open,
  });

  const customerName = (id: string): string =>
    customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;

  const createMut = useMutation({
    mutationFn: (payload: ContractCreate) => api.post<Contract>('/v1/contracts', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contracts'] });
      setOpen(false);
      setForm(EMPTY_FORM);
    },
  });

  const columns: Array<Column<Contract>> = [
    {
      key: 'contract_number',
      header: 'Contract #',
      render: (c) => <span className="font-medium text-white">{c.contract_number}</span>,
    },
    { key: 'customer_id', header: 'Customer', render: (c) => customerName(c.customer_id) },
    { key: 'term_months', header: 'Term', render: (c) => `${c.term_months} mo` },
    {
      key: 'auto_renew',
      header: 'Auto-renew',
      render: (c) => (c.auto_renew ? <Badge tone="cyan">Yes</Badge> : <Badge tone="neutral">No</Badge>),
    },
    { key: 'start_date', header: 'Start', render: (c) => c.start_date ?? '—' },
    {
      key: 'status',
      header: 'Status',
      render: (c) => <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>,
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
          eyebrow="COMMERCIAL · AGREEMENTS"
          title="Contracts"
          description="Signed commercial agreements, their terms, and lifecycle status."
        />
        <button type="button" className="btn-primary" onClick={() => setOpen(true)}>
          + New Contract
        </button>
      </div>

      {isLoading ? (
        <Spinner label="Loading contracts…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable
          columns={columns}
          rows={data ?? []}
          rowKey={(c) => c.id}
          empty={<EmptyState title="No contracts yet" hint="Create a contract once a deal is ready to be papered." />}
        />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="New Contract">
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div>
            <label className="label" htmlFor="contract_number">Contract Number</label>
            <input
              id="contract_number"
              className="input"
              required
              placeholder="NEO-2026-001"
              value={form.contract_number}
              onChange={(e) => setForm({ ...form, contract_number: e.target.value })}
            />
          </div>
          <div>
            <label className="label" htmlFor="customer_id">Customer</label>
            <select
              id="customer_id"
              className="input"
              required
              value={form.customer_id}
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            >
              <option value="" disabled>
                {customersQuery.isLoading ? 'Loading customers…' : 'Select a customer'}
              </option>
              {customersQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.legal_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="term_months">Term (months)</label>
            <input
              id="term_months"
              type="number"
              min={1}
              className="input"
              required
              value={form.term_months}
              onChange={(e) => setForm({ ...form, term_months: Number(e.target.value) })}
            />
          </div>

          {createMut.isError && <ErrorState error={createMut.error} />}

          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Creating…' : 'Create Contract'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
