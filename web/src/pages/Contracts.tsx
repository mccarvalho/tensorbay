// Contracts — list with search, create, edit, and delete (write-gated).
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

type ContractStatus = 'DRAFT' | 'ACTIVE' | 'AMENDED' | 'RENEWED' | 'TERMINATED' | 'EXPIRED';
const CONTRACT_STATUSES: ContractStatus[] = ['DRAFT', 'ACTIVE', 'AMENDED', 'RENEWED', 'TERMINATED', 'EXPIRED'];

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
interface CustomerLite { id: string; legal_name: string }

interface ContractForm {
  contract_number: string;
  customer_id: string;
  term_months: number;
  status: ContractStatus;
  start_date: string | null;
  end_date: string | null;
  auto_renew: boolean;
}

const STATUS_TONE: Record<ContractStatus, BadgeTone> = {
  DRAFT: 'neutral', ACTIVE: 'success', AMENDED: 'cyan', RENEWED: 'cyan', TERMINATED: 'flamingo', EXPIRED: 'warning',
};

const emptyForm = (): ContractForm => ({
  contract_number: '', customer_id: '', term_months: 12,
  status: 'DRAFT', start_date: null, end_date: null, auto_renew: false,
});

export default function Contracts() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('contract.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ContractForm>(emptyForm);
  const [search, setSearch] = useState('');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api.get<Contract[]>('/v1/contracts?limit=200'),
  });
  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
  });
  const customerName = (id: string) => customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;

  const reset = () => { setEditId(null); setForm(emptyForm()); };
  const save = useMutation({
    mutationFn: () => {
      if (editId) {
        const payload = {
          contract_number: form.contract_number, status: form.status, term_months: form.term_months,
          start_date: form.start_date, end_date: form.end_date, auto_renew: form.auto_renew,
        };
        return api.patch<Contract>(`/v1/contracts/${editId}`, payload);
      }
      return api.post<Contract>('/v1/contracts', {
        contract_number: form.contract_number, customer_id: form.customer_id, term_months: form.term_months,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contracts'] });
      toast.success(editId ? 'Contract updated' : 'Contract created');
      setOpen(false); reset();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not save contract')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/contracts/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['contracts'] }); toast.success('Contract deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete contract')),
  });

  function openEdit(c: Contract) {
    setEditId(c.id);
    setForm({
      contract_number: c.contract_number, customer_id: c.customer_id, term_months: c.term_months,
      status: c.status, start_date: c.start_date, end_date: c.end_date, auto_renew: c.auto_renew,
    });
    setOpen(true);
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data ?? [];
    return (data ?? []).filter((c) =>
      `${c.contract_number} ${customerName(c.customer_id)} ${c.status}`.toLowerCase().includes(q),
    );
  }, [data, search, customersQuery.data]);

  const columns: Array<Column<Contract>> = [
    { key: 'contract_number', header: 'Contract #', render: (c) => <span className="font-medium text-white">{c.contract_number}</span> },
    { key: 'customer_id', header: 'Customer', render: (c) => customerName(c.customer_id) },
    { key: 'term_months', header: 'Term', render: (c) => `${c.term_months} mo` },
    { key: 'auto_renew', header: 'Auto-renew', render: (c) => (c.auto_renew ? <Badge tone="cyan">Yes</Badge> : <Badge tone="neutral">No</Badge>) },
    { key: 'start_date', header: 'Start', render: (c) => c.start_date ?? '—' },
    { key: 'status', header: 'Status', render: (c) => <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge> },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (c) => (
        <div className="flex justify-end gap-2">
          <Link to={`/contracts/${c.id}`} className="btn-ghost px-2.5 py-1 text-xs">View →</Link>
          {canWrite && (
            <>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(c)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete contract ${c.contract_number}?`)) del.mutate(c.id); }}>Delete</button>
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
          eyebrow="COMMERCIAL · AGREEMENTS"
          title="Contracts"
          description="Signed commercial agreements, their terms, and lifecycle status."
        />
        {canWrite && (
          <button type="button" className="btn-primary" onClick={() => { reset(); setOpen(true); }}>+ New Contract</button>
        )}
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by number, customer, status…" />

      {isLoading ? (
        <Spinner label="Loading contracts…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable columns={columns} rows={filtered} rowKey={(c) => c.id}
          empty={<EmptyState title={search ? 'No matches' : 'No contracts yet'} hint={search ? 'Try a different search.' : 'Create a contract once a deal is ready to be papered.'} />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Contract' : 'New Contract'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div>
            <label className="label" htmlFor="contract_number">Contract Number</label>
            <input id="contract_number" className="input" required placeholder="NEO-2026-001"
              value={form.contract_number} onChange={(e) => setForm({ ...form, contract_number: e.target.value })} />
          </div>
          {!editId && (
            <div>
              <label className="label" htmlFor="customer_id">Customer</label>
              <select id="customer_id" className="input" required value={form.customer_id}
                onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                <option value="" disabled>{customersQuery.isLoading ? 'Loading customers…' : 'Select a customer'}</option>
                {customersQuery.data?.map((c) => <option key={c.id} value={c.id}>{c.legal_name}</option>)}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="term_months">Term (months)</label>
              <input id="term_months" type="number" min={1} className="input" required
                value={form.term_months} onChange={(e) => setForm({ ...form, term_months: Number(e.target.value) })} />
            </div>
            {editId && (
              <div>
                <label className="label" htmlFor="ctr_status">Status</label>
                <select id="ctr_status" className="input" value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value as ContractStatus })}>
                  {CONTRACT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            )}
          </div>
          {editId && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label" htmlFor="ctr_start">Start Date</label>
                  <input id="ctr_start" type="date" className="input" value={form.start_date ?? ''}
                    onChange={(e) => setForm({ ...form, start_date: e.target.value || null })} />
                </div>
                <div>
                  <label className="label" htmlFor="ctr_end">End Date</label>
                  <input id="ctr_end" type="date" className="input" value={form.end_date ?? ''}
                    onChange={(e) => setForm({ ...form, end_date: e.target.value || null })} />
                </div>
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm text-white">
                <input type="checkbox" checked={form.auto_renew}
                  onChange={(e) => setForm({ ...form, auto_renew: e.target.checked })} />
                Auto-renew
              </label>
            </>
          )}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Contract'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
