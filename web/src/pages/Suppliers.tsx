// Suppliers / Distributors — procurement counterparties. List with search,
// create/edit/delete (supplier.write gated), plus a contacts sub-modal.
import { useMemo, useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from '../components/toast';
import { SUPPLIER_TIERS, SUPPLIER_STATUSES, type SupplierTier, type SupplierStatus } from '../constants';
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

interface Supplier {
  id: string;
  name: string;
  legal_name: string | null;
  tier: SupplierTier;
  status: SupplierStatus;
  country: string | null;
  website: string | null;
  account_manager: string | null;
  notes: string | null;
  created_at: string;
}

interface SupplierContact {
  id: string;
  supplier_id: string;
  name: string;
  role: string | null;
  email: string | null;
  phone: string | null;
}

interface SupplierForm {
  name: string;
  legal_name: string;
  tier: SupplierTier;
  status: SupplierStatus;
  country: string;
  website: string;
  account_manager: string;
  notes: string;
}

const TIER_TONE: Record<SupplierTier, BadgeTone> = {
  OEM: 'cyan', DISTRIBUTOR: 'grape', CLOUD: 'flamingo', BROKER: 'neutral',
};
const STATUS_TONE: Record<SupplierStatus, BadgeTone> = {
  ACTIVE: 'success', INACTIVE: 'neutral',
};

const emptyForm = (): SupplierForm => ({
  name: '', legal_name: '', tier: 'DISTRIBUTOR', status: 'ACTIVE',
  country: '', website: '', account_manager: '', notes: '',
});

export default function Suppliers() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('supplier.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<SupplierForm>(emptyForm);
  const [search, setSearch] = useState('');
  const [contactsFor, setContactsFor] = useState<Supplier | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => api.get<Supplier[]>('/v1/suppliers?limit=200'),
  });

  const reset = () => { setEditId(null); setForm(emptyForm()); };
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name,
        legal_name: form.legal_name || null,
        tier: form.tier,
        status: form.status,
        country: form.country || null,
        website: form.website || null,
        account_manager: form.account_manager || null,
        notes: form.notes || null,
      };
      return editId
        ? api.patch<Supplier>(`/v1/suppliers/${editId}`, payload)
        : api.post<Supplier>('/v1/suppliers', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success(editId ? 'Supplier updated' : 'Supplier created');
      setOpen(false); reset();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not save supplier')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/suppliers/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['suppliers'] }); toast.success('Supplier deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete supplier')),
  });

  function openEdit(s: Supplier) {
    setEditId(s.id);
    setForm({
      name: s.name, legal_name: s.legal_name ?? '', tier: s.tier, status: s.status,
      country: s.country ?? '', website: s.website ?? '',
      account_manager: s.account_manager ?? '', notes: s.notes ?? '',
    });
    setOpen(true);
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data ?? [];
    return (data ?? []).filter((s) =>
      `${s.name} ${s.legal_name ?? ''} ${s.tier} ${s.country ?? ''} ${s.account_manager ?? ''}`.toLowerCase().includes(q),
    );
  }, [data, search]);

  const columns: Array<Column<Supplier>> = [
    {
      key: 'name', header: 'Supplier',
      render: (s) => (
        <div className="flex flex-col">
          <span className="font-medium text-white">{s.name}</span>
          {s.legal_name && <span className="text-xs text-grape-soft">{s.legal_name}</span>}
        </div>
      ),
    },
    { key: 'tier', header: 'Tier', render: (s) => <Badge tone={TIER_TONE[s.tier]}>{s.tier}</Badge> },
    { key: 'status', header: 'Status', render: (s) => <Badge tone={STATUS_TONE[s.status]}>{s.status}</Badge> },
    { key: 'country', header: 'Country', render: (s) => s.country || '—' },
    { key: 'account_manager', header: 'Account Manager', render: (s) => s.account_manager || '—' },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (s) => (
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setContactsFor(s)}>Contacts</button>
          {canWrite && (
            <>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(s)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete supplier ${s.name}?`)) del.mutate(s.id); }}>Delete</button>
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
          eyebrow="PROCUREMENT · SUPPLIERS"
          title="Suppliers & Distributors"
          description="OEMs, distributors, cloud providers, and brokers we procure GPU capacity from. Link negotiations to a supplier from the Capacity page."
        />
        {canWrite && (
          <button type="button" className="btn-primary" onClick={() => { reset(); setOpen(true); }}>+ New Supplier</button>
        )}
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by name, tier, country, manager…" />

      {isLoading ? (
        <Spinner label="Loading suppliers…" />
      ) : isError ? (
        <ErrorState error={error} />
      ) : (
        <DataTable columns={columns} rows={filtered} rowKey={(s) => s.id}
          empty={<EmptyState title={search ? 'No matches' : 'No suppliers yet'} hint={search ? 'Try a different search.' : 'Add the distributors and OEMs you negotiate GPU capacity with.'} />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Supplier' : 'New Supplier'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div>
            <label className="label" htmlFor="sup_name">Name</label>
            <input id="sup_name" className="input" required placeholder="Oracle"
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="sup_legal">Legal Name</label>
            <input id="sup_legal" className="input" placeholder="Oracle Corporation"
              value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="sup_tier">Tier</label>
              <select id="sup_tier" className="input" value={form.tier}
                onChange={(e) => setForm({ ...form, tier: e.target.value as SupplierTier })}>
                {SUPPLIER_TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="sup_status">Status</label>
              <select id="sup_status" className="input" value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as SupplierStatus })}>
                {SUPPLIER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="sup_country">Country</label>
              <input id="sup_country" className="input" maxLength={2} placeholder="US"
                value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })} />
            </div>
            <div>
              <label className="label" htmlFor="sup_mgr">Account Manager</label>
              <input id="sup_mgr" className="input" placeholder="Our owner for this supplier"
                value={form.account_manager} onChange={(e) => setForm({ ...form, account_manager: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="sup_web">Website</label>
            <input id="sup_web" className="input" placeholder="https://oracle.com"
              value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="sup_notes">Notes</label>
            <textarea id="sup_notes" className="input" rows={2}
              value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Supplier'}
            </button>
          </div>
        </form>
      </Modal>

      {contactsFor && (
        <ContactsModal supplier={contactsFor} canWrite={canWrite} onClose={() => setContactsFor(null)} />
      )}
    </div>
  );
}

function ContactsModal({ supplier, canWrite, onClose }: { supplier: Supplier; canWrite: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({ name: '', role: '', email: '', phone: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['supplier-contacts', supplier.id],
    queryFn: () => api.get<SupplierContact[]>(`/v1/suppliers/${supplier.id}/contacts`),
  });

  const add = useMutation({
    mutationFn: () => api.post<SupplierContact>(`/v1/suppliers/${supplier.id}/contacts`, {
      name: form.name, role: form.role || null, email: form.email || null, phone: form.phone || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['supplier-contacts', supplier.id] });
      toast.success('Contact added');
      setForm({ name: '', role: '', email: '', phone: '' });
    },
    onError: (e) => toast.error(errMessage(e, 'Could not add contact')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/suppliers/${supplier.id}/contacts/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['supplier-contacts', supplier.id] }); toast.success('Contact removed'); },
    onError: (e) => toast.error(errMessage(e, 'Could not remove contact')),
  });

  return (
    <Modal open onClose={onClose} title={`Contacts · ${supplier.name}`}>
      <div className="flex flex-col gap-4">
        {isLoading ? (
          <Spinner label="Loading contacts…" />
        ) : (data ?? []).length === 0 ? (
          <p className="text-sm text-grape-soft">No contacts yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {(data ?? []).map((c) => (
              <li key={c.id} className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 px-3 py-2">
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-white">{c.name}{c.role ? ` · ${c.role}` : ''}</span>
                  <span className="text-xs text-grape-soft">{[c.email, c.phone].filter(Boolean).join(' · ') || '—'}</span>
                </div>
                {canWrite && (
                  <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                    onClick={() => del.mutate(c.id)}>Remove</button>
                )}
              </li>
            ))}
          </ul>
        )}

        {canWrite && (
          <form className="flex flex-col gap-3 border-t border-white/5 pt-4"
            onSubmit={(e: FormEvent) => { e.preventDefault(); add.mutate(); }}>
            <div className="grid grid-cols-2 gap-3">
              <input className="input" required placeholder="Name" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className="input" placeholder="Role" value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })} />
              <input className="input" placeholder="Email" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} />
              <input className="input" placeholder="Phone" value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div className="flex justify-end">
              <button type="submit" className="btn-primary" disabled={add.isPending}>
                {add.isPending ? 'Adding…' : '+ Add Contact'}
              </button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
}
