// Customers — list + create (required fields only), matching the customer schema.
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

type CustomerStatus =
  | 'PROSPECT'
  | 'ACTIVE'
  | 'INACTIVE'
  | 'SUSPENDED'
  | 'CHURNED';
type CreditStatus = 'GOOD' | 'WATCH' | 'HOLD' | 'BLOCKED';

interface Customer {
  id: string;
  legal_name: string;
  trading_name: string | null;
  tax_id: string | null;
  country: string;
  currency: string;
  status: CustomerStatus;
  credit_status: CreditStatus;
  industry: string | null;
  created_at: string;
}

interface CustomerCreate {
  legal_name: string;
  trading_name: string;
  tax_id: string;
  country: string;
  currency: string;
}

const STATUS_TONE: Record<CustomerStatus, BadgeTone> = {
  PROSPECT: 'cyan',
  ACTIVE: 'success',
  INACTIVE: 'neutral',
  SUSPENDED: 'warning',
  CHURNED: 'flamingo',
};

const CREDIT_TONE: Record<CreditStatus, BadgeTone> = {
  GOOD: 'success',
  WATCH: 'warning',
  HOLD: 'warning',
  BLOCKED: 'flamingo',
};

const EMPTY_FORM: CustomerCreate = {
  legal_name: '',
  trading_name: '',
  tax_id: '',
  country: 'BR',
  currency: 'USD',
};

export default function Customers() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CustomerCreate>(EMPTY_FORM);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['customers'],
    queryFn: () => api.get<Customer[]>('/v1/customers?limit=200'),
  });

  const createMut = useMutation({
    mutationFn: (payload: CustomerCreate) =>
      api.post<Customer>('/v1/customers', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customers'] });
      setOpen(false);
      setForm(EMPTY_FORM);
    },
  });

  const columns: Array<Column<Customer>> = [
    {
      key: 'legal_name',
      header: 'Legal Name',
      render: (c) => (
        <div className="flex flex-col">
          <span className="font-medium text-white">{c.legal_name}</span>
          {c.trading_name && (
            <span className="text-xs text-grape-soft">{c.trading_name}</span>
          )}
        </div>
      ),
    },
    { key: 'country', header: 'Country' },
    { key: 'currency', header: 'Currency' },
    {
      key: 'status',
      header: 'Status',
      render: (c) => <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>,
    },
    {
      key: 'credit_status',
      header: 'Credit',
      render: (c) => <Badge tone={CREDIT_TONE[c.credit_status]}>{c.credit_status}</Badge>,
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
          eyebrow="COMMERCIAL · ACCOUNTS"
          title="Customers"
          description="Every account in the pipeline and book of business, with status and credit posture."
        />
        <button type="button" className="btn-primary" onClick={() => setOpen(true)}>
          + New Customer
        </button>
      </div>

      {isLoading ? (
        <Spinner label="Loading customers…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable
          columns={columns}
          rows={data ?? []}
          rowKey={(c) => c.id}
          empty={
            <EmptyState
              title="No customers yet"
              hint="Add your first account to start building the pipeline."
            />
          }
        />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="New Customer">
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div>
            <label className="label" htmlFor="legal_name">Legal Name</label>
            <input
              id="legal_name"
              className="input"
              required
              placeholder="Acme GPU Ltda"
              value={form.legal_name}
              onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
            />
          </div>
          <div>
            <label className="label" htmlFor="trading_name">Trading Name</label>
            <input
              id="trading_name"
              className="input"
              placeholder="Acme"
              value={form.trading_name}
              onChange={(e) => setForm({ ...form, trading_name: e.target.value })}
            />
          </div>
          <div>
            <label className="label" htmlFor="tax_id">Tax ID</label>
            <input
              id="tax_id"
              className="input"
              placeholder="12.345.678/0001-90"
              value={form.tax_id}
              onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="country">Country</label>
              <input
                id="country"
                className="input"
                required
                maxLength={2}
                placeholder="BR"
                value={form.country}
                onChange={(e) =>
                  setForm({ ...form, country: e.target.value.toUpperCase() })
                }
              />
            </div>
            <div>
              <label className="label" htmlFor="currency">Currency</label>
              <input
                id="currency"
                className="input"
                required
                maxLength={3}
                placeholder="USD"
                value={form.currency}
                onChange={(e) =>
                  setForm({ ...form, currency: e.target.value.toUpperCase() })
                }
              />
            </div>
          </div>

          {createMut.isError && <ErrorState error={createMut.error} />}

          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? 'Creating…' : 'Create Customer'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
