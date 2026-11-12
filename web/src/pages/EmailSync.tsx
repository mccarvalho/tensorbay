// Email — customer emails captured from Gmail. Emails that match a customer
// contact land on that customer's timeline automatically; crm@ emails that match
// nobody wait here to be assigned. Super Admins manage which mailboxes are read.
import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from '../components/toast';
import {
  SectionHeader, Spinner, ErrorState, EmptyState, DataTable, Badge, Modal,
  type Column,
} from '../components/ui';

interface Mailbox {
  id: string; address: string; enabled: boolean; capture_unmatched: boolean;
  last_sync_at: string | null; last_error: string | null; last_logged: number; total_logged: number;
}
interface SyncStatus {
  configured: boolean; service_account: string | null; mailboxes: Mailbox[]; pending_unmatched: number;
}
interface Unmatched {
  id: string; mailbox: string; direction: 'IN' | 'OUT'; from_addr: string; external_addrs: string;
  subject: string; body_text: string | null; sent_at: string; status: string;
}
interface CustomerLite { id: string; legal_name: string }

const when = (iso: string) => new Date(iso).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });

export default function EmailSync() {
  const isAdmin = hasPermission('user.admin');
  const status = useQuery({ queryKey: ['email-status'], queryFn: () => api.get<SyncStatus>('/v1/email-sync/status') });

  return (
    <div className="flex flex-col gap-8">
      <SectionHeader
        eyebrow="CRM · EMAIL"
        title="Email"
        description="Emails with your customers are added to their timeline automatically. Send or BCC anything else to crm@tensorbay.io; if it doesn't match a known contact it waits below."
      />
      {status.isLoading ? <Spinner label="Loading…" /> : status.isError ? <ErrorState error={status.error} /> : (
        <>
          {!status.data!.configured && (
            <div className="card border border-flamingo/40 text-sm">
              <span className="font-semibold text-flamingo">Gmail is not connected yet.</span>{' '}
              <span className="text-grape-soft">
                A Google Workspace admin has to authorize the service account before any email is read.
              </span>
            </div>
          )}
          <UnmatchedQueue />
          {isAdmin && <Mailboxes status={status.data!} />}
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
function UnmatchedQueue() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('customer.write');
  const [assigning, setAssigning] = useState<Unmatched | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const list = useQuery({ queryKey: ['email-unmatched'], queryFn: () => api.get<Unmatched[]>('/v1/email-sync/unmatched') });
  const refresh = () => { qc.invalidateQueries({ queryKey: ['email-unmatched'] }); qc.invalidateQueries({ queryKey: ['email-status'] }); };
  const dismiss = useMutation({
    mutationFn: (id: string) => api.post<Unmatched>(`/v1/email-sync/unmatched/${id}/dismiss`, {}),
    onSuccess: () => { toast.success('Dismissed'); refresh(); },
    onError: (e) => toast.error(errMessage(e, 'Could not dismiss')),
  });

  const columns: Array<Column<Unmatched>> = [
    { key: 'when', header: 'Date', render: (m) => <span className="text-xs text-grape-soft">{when(m.sent_at)}</span> },
    { key: 'dir', header: '', render: (m) => <Badge tone={m.direction === 'IN' ? 'cyan' : 'grape'}>{m.direction === 'IN' ? 'Received' : 'Sent'}</Badge> },
    {
      key: 'who', header: 'From / with',
      render: (m) => (
        <div className="flex flex-col">
          <span className="text-white">{m.from_addr}</span>
          <span className="text-xs text-grape-soft">{m.external_addrs.split(',').join(', ')}</span>
        </div>
      ),
    },
    {
      key: 'subject', header: 'Subject',
      render: (m) => (
        <div className="flex flex-col gap-1">
          <button type="button" className="text-left font-medium text-white hover:text-cyan" onClick={() => setOpenId(openId === m.id ? null : m.id)}>
            {m.subject}
          </button>
          {openId === m.id && <pre className="max-h-60 overflow-auto whitespace-pre-wrap text-xs text-grape-soft">{m.body_text || '(no text)'}</pre>}
        </div>
      ),
    },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (m) => canWrite ? (
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-primary px-2.5 py-1 text-xs" onClick={() => setAssigning(m)}>Assign</button>
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" disabled={dismiss.isPending}
            onClick={() => { if (confirm('Dismiss this email? Its content will be deleted.')) dismiss.mutate(m.id); }}>Dismiss</button>
        </div>
      ) : null,
    },
  ];

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg">Needs a customer</h2>
      {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} /> : (
        <DataTable columns={columns} rows={list.data ?? []} rowKey={(m) => m.id}
          empty={<EmptyState title="Nothing waiting" hint="Emails to crm@ that match no customer contact show up here." />} />
      )}
      {assigning && <AssignModal item={assigning} onClose={() => setAssigning(null)} onDone={() => { setAssigning(null); refresh(); }} />}
    </section>
  );
}

function AssignModal({ item, onClose, onDone }: { item: Unmatched; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const externals = item.external_addrs.split(',').filter(Boolean);
  const [customerId, setCustomerId] = useState('');
  const [contactEmail, setContactEmail] = useState(externals[0] ?? '');
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [createContact, setCreateContact] = useState(true);
  const customers = useQuery({ queryKey: ['customers-lite'], queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=500') });

  const assign = useMutation({
    mutationFn: () => api.post<Unmatched>(`/v1/email-sync/unmatched/${item.id}/assign`, {
      customer_id: customerId, create_contact: createContact,
      contact_email: contactEmail || null, contact_name: name.trim() || null, contact_role: role.trim() || null,
    }),
    onSuccess: () => { toast.success('Added to the customer timeline'); onDone(); },
    onError: (e) => toast.error(errMessage(e, 'Could not assign')),
  });

  return (
    <Modal open onClose={onClose} title="Assign email to a customer">
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); assign.mutate(); }}>
        <p className="text-sm text-grape-soft">“{item.subject}”</p>
        <div>
          <label className="label" htmlFor="as_cust">Customer</label>
          <select id="as_cust" className="input" required value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">— choose —</option>
            {(customers.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.legal_name}</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-white">
          <input type="checkbox" checked={createContact} onChange={(e) => setCreateContact(e.target.checked)} />
          Save the sender as a contact (future emails match automatically)
        </label>
        {createContact && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="as_email">Email</label>
              <select id="as_email" className="input" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)}>
                {externals.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="as_name">Name</label>
              <input id="as_name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <label className="label" htmlFor="as_role">Role</label>
              <input id="as_role" className="input" value={role} onChange={(e) => setRole(e.target.value)} placeholder="optional" />
            </div>
          </div>
        )}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={assign.isPending || !customerId}>
            {assign.isPending ? 'Saving…' : 'Assign'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
function Mailboxes({ status }: { status: SyncStatus }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [address, setAddress] = useState('');
  const [capture, setCapture] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ['email-status'] });
  const add = useMutation({
    mutationFn: () => api.post<Mailbox>('/v1/email-sync/mailboxes', { address: address.trim(), capture_unmatched: capture }),
    onSuccess: () => { toast.success('Mailbox added'); setAddress(''); setCapture(false); refresh(); },
    onError: (e) => toast.error(errMessage(e, 'Could not add mailbox')),
  });
  const patch = useMutation({
    mutationFn: (v: { id: string; body: Partial<Mailbox> }) => api.patch<Mailbox>(`/v1/email-sync/mailboxes/${v.id}`, v.body),
    onSuccess: refresh,
    onError: (e) => toast.error(errMessage(e, 'Could not update mailbox')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/email-sync/mailboxes/${id}`),
    onSuccess: () => { toast.success('Mailbox removed'); refresh(); },
    onError: (e) => toast.error(errMessage(e, 'Could not remove mailbox')),
  });
  const sync = useMutation({
    mutationFn: (id: string) => api.post<{ mailbox: string; logged: number; unmatched: number; skipped: number; error: string | null }>(`/v1/email-sync/mailboxes/${id}/sync`, {}),
    onSuccess: (r) => {
      refresh(); qc.invalidateQueries({ queryKey: ['email-unmatched'] });
      if (r.error) toast.error(`Sync failed: ${r.error}`);
      else toast.success(`${r.mailbox}: ${r.logged} logged, ${r.unmatched} to triage, ${r.skipped} skipped`);
    },
    onError: (e) => toast.error(errMessage(e, 'Sync failed')),
  });

  const columns: Array<Column<Mailbox>> = [
    { key: 'addr', header: 'Mailbox', render: (m) => <span className="font-medium text-white">{m.address}</span> },
    { key: 'kind', header: 'Mode', render: (m) => m.capture_unmatched ? <Badge tone="cyan">shared inbox</Badge> : <Badge tone="grape">customer emails only</Badge> },
    { key: 'on', header: 'Enabled', render: (m) => (
      <input type="checkbox" checked={m.enabled} onChange={(e) => patch.mutate({ id: m.id, body: { enabled: e.target.checked } })} aria-label={`Enable ${m.address}`} />
    ) },
    { key: 'last', header: 'Last sync', render: (m) => (
      <div className="flex flex-col text-xs">
        <span className="text-grape-soft">{m.last_sync_at ? when(m.last_sync_at) : 'never'}</span>
        {m.last_error && <span className="text-flamingo">{m.last_error.slice(0, 120)}</span>}
      </div>
    ) },
    { key: 'n', header: 'Logged', className: 'text-right', render: (m) => m.total_logged },
    { key: 'actions', header: '', className: 'text-right', render: (m) => (
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs" disabled={sync.isPending || !status.configured} onClick={() => sync.mutate(m.id)}>Sync now</button>
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
          onClick={() => { if (confirm(`Stop reading ${m.address}? Emails already logged stay.`)) del.mutate(m.id); }}>Remove</button>
      </div>
    ) },
  ];

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg">Connected mailboxes</h2>
      <p className="text-sm text-grape-soft">
        Read-only access through Google service account{' '}
        <span className="text-white">{status.service_account ?? '(not set up)'}</span>. A mailbox only works once the
        account is authorized for the domain in the Google Admin console.
      </p>
      <DataTable columns={columns} rows={status.mailboxes} rowKey={(m) => m.id}
        empty={<EmptyState title="No mailboxes" hint="Add crm@tensorbay.io below." />} />
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e: FormEvent) => { e.preventDefault(); add.mutate(); }}>
        <div>
          <label className="label" htmlFor="mb_addr">Add mailbox</label>
          <input id="mb_addr" type="email" required className="input min-w-[260px]" placeholder="crm@tensorbay.io"
            value={address} onChange={(e) => setAddress(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-white">
          <input type="checkbox" checked={capture} onChange={(e) => setCapture(e.target.checked)} />
          Shared inbox (keep emails that match no customer for triage)
        </label>
        <button type="submit" className="btn-primary" disabled={add.isPending}>Add</button>
      </form>
    </section>
  );
}
