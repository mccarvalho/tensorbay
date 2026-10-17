// Customers — list with search, create, edit, and delete (write-gated).
import { useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from '../components/toast';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  SearchInput,
  type BadgeTone,
  type Column,
} from '../components/ui';

type CustomerStatus = 'PROSPECT' | 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'CHURNED';
type CreditStatus = 'GOOD' | 'WATCH' | 'HOLD' | 'BLOCKED';
const CUSTOMER_STATUSES: CustomerStatus[] = ['PROSPECT', 'ACTIVE', 'INACTIVE', 'SUSPENDED', 'CHURNED'];
const CREDIT_STATUSES: CreditStatus[] = ['GOOD', 'WATCH', 'HOLD', 'BLOCKED'];

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
  account_owner: string | null;
  created_at: string;
}

interface CustomerForm {
  legal_name: string;
  trading_name: string;
  tax_id: string;
  country: string;
  currency: string;
  status: CustomerStatus;
  credit_status: CreditStatus;
  industry: string;
  account_owner: string;
}

const STATUS_TONE: Record<CustomerStatus, BadgeTone> = {
  PROSPECT: 'cyan', ACTIVE: 'success', INACTIVE: 'neutral', SUSPENDED: 'warning', CHURNED: 'flamingo',
};
const CREDIT_TONE: Record<CreditStatus, BadgeTone> = {
  GOOD: 'success', WATCH: 'warning', HOLD: 'warning', BLOCKED: 'flamingo',
};

const emptyForm = (): CustomerForm => ({
  legal_name: '', trading_name: '', tax_id: '', country: 'BR', currency: 'USD',
  status: 'PROSPECT', credit_status: 'GOOD', industry: '', account_owner: '',
});

export default function Customers() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('customer.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<CustomerForm>(emptyForm);
  const [search, setSearch] = useState('');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['customers'],
    queryFn: () => api.get<Customer[]>('/v1/customers?limit=200'),
  });

  const reset = () => { setEditId(null); setForm(emptyForm()); };
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        legal_name: form.legal_name,
        trading_name: form.trading_name || null,
        tax_id: form.tax_id || null,
        country: form.country,
        currency: form.currency,
        ...(editId ? {
          status: form.status,
          credit_status: form.credit_status,
          industry: form.industry || null,
          account_owner: form.account_owner || null,
        } : {}),
      };
      return editId
        ? api.patch<Customer>(`/v1/customers/${editId}`, payload)
        : api.post<Customer>('/v1/customers', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customers'] });
      toast.success(editId ? 'Customer updated' : 'Customer created');
      setOpen(false); reset();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not save customer')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/customers/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['customers'] }); toast.success('Customer deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete customer')),
  });

  function openEdit(c: Customer) {
    setEditId(c.id);
    setForm({
      legal_name: c.legal_name, trading_name: c.trading_name ?? '', tax_id: c.tax_id ?? '',
      country: c.country, currency: c.currency, status: c.status, credit_status: c.credit_status,
      industry: c.industry ?? '', account_owner: c.account_owner ?? '',
    });
    setOpen(true);
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data ?? [];
    return (data ?? []).filter((c) =>
      `${c.legal_name} ${c.trading_name ?? ''} ${c.country} ${c.industry ?? ''} ${c.status}`.toLowerCase().includes(q),
    );
  }, [data, search]);

  const columns: Array<Column<Customer>> = [
    {
      key: 'legal_name', header: 'Legal Name',
      render: (c) => (
        <div className="flex flex-col">
          <span className="font-medium text-white">{c.legal_name}</span>
          {c.trading_name && <span className="text-xs text-grape-soft">{c.trading_name}</span>}
        </div>
      ),
    },
    { key: 'country', header: 'Country' },
    { key: 'currency', header: 'Currency' },
    { key: 'status', header: 'Status', render: (c) => <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge> },
    { key: 'credit_status', header: 'Credit', render: (c) => <Badge tone={CREDIT_TONE[c.credit_status]}>{c.credit_status}</Badge> },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (c) => (
        <div className="flex justify-end gap-2">
          <Link to={`/customers/${c.id}`} className="btn-ghost px-2.5 py-1 text-xs">Open CRM →</Link>
          {canWrite && (
            <>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(c)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete customer ${c.legal_name}?`)) del.mutate(c.id); }}>Delete</button>
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
          eyebrow="COMMERCIAL · ACCOUNTS"
          title="Customers"
          description="Every account in the pipeline and book of business, with status and credit posture."
        />
        {canWrite && (
          <button type="button" className="btn-primary" onClick={() => { reset(); setOpen(true); }}>+ New Customer</button>
        )}
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by name, country, industry…" />

      {isLoading ? (
        <Spinner label="Loading customers…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable columns={columns} rows={filtered} rowKey={(c) => c.id}
          empty={<EmptyState title={search ? 'No matches' : 'No customers yet'} hint={search ? 'Try a different search.' : 'Add your first account to start building the pipeline.'} />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Customer' : 'New Customer'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div>
            <label className="label" htmlFor="legal_name">Legal Name</label>
            <input id="legal_name" className="input" required placeholder="Acme GPU Ltda"
              value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="trading_name">Trading Name</label>
            <input id="trading_name" className="input" placeholder="Acme"
              value={form.trading_name} onChange={(e) => setForm({ ...form, trading_name: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="tax_id">Tax ID</label>
            <input id="tax_id" className="input" placeholder="12.345.678/0001-90"
              value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="country">Country</label>
              <input id="country" className="input" required maxLength={2} placeholder="BR"
                value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })} />
            </div>
            <div>
              <label className="label" htmlFor="currency">Currency</label>
              <input id="currency" className="input" required maxLength={3} placeholder="USD"
                value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} />
            </div>
          </div>
          {editId && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label" htmlFor="cust_status">Status</label>
                  <select id="cust_status" className="input" value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value as CustomerStatus })}>
                    {CUSTOMER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="cust_credit">Credit Status</label>
                  <select id="cust_credit" className="input" value={form.credit_status}
                    onChange={(e) => setForm({ ...form, credit_status: e.target.value as CreditStatus })}>
                    {CREDIT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label" htmlFor="cust_industry">Industry</label>
                  <input id="cust_industry" className="input" value={form.industry}
                    onChange={(e) => setForm({ ...form, industry: e.target.value })} />
                </div>
                <div>
                  <label className="label" htmlFor="cust_owner">Account Owner</label>
                  <input id="cust_owner" className="input" value={form.account_owner}
                    onChange={(e) => setForm({ ...form, account_owner: e.target.value })} />
                </div>
              </div>
            </>
          )}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Customer'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
