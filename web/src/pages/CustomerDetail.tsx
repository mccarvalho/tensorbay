// Customer Detail / CRM — contacts + pre-proposal activity timeline.
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  Badge,
  Modal,
  type BadgeTone,
} from '../components/ui';

// --------------------------------------------------------------------------- //
type ContactType = 'COMMERCIAL' | 'TECHNICAL' | 'FINANCE' | 'BILLING' | 'EXECUTIVE';
type ActivityType = 'CALL' | 'EMAIL' | 'MEETING' | 'NOTE' | 'DEMO' | 'OTHER';

const CONTACT_TYPES: ContactType[] = ['COMMERCIAL', 'TECHNICAL', 'FINANCE', 'BILLING', 'EXECUTIVE'];
const ACTIVITY_TYPES: ActivityType[] = ['CALL', 'EMAIL', 'MEETING', 'NOTE', 'DEMO', 'OTHER'];

interface Customer {
  id: string;
  legal_name: string;
  trading_name: string | null;
  country: string | null;
  currency: string | null;
  status: string;
  credit_status: string;
  industry: string | null;
  account_owner: string | null;
}

interface Contact {
  id: string;
  customer_id: string;
  type: ContactType;
  name: string;
  email: string | null;
  phone: string | null;
}

interface Activity {
  id: string;
  customer_id: string;
  contact_id: string | null;
  type: ActivityType;
  subject: string;
  notes: string | null;
  outcome: string | null;
  occurred_at: string;
  next_follow_up_date: string | null;
  created_by: string | null;
}

const CONTACT_TONE: Record<ContactType, BadgeTone> = {
  COMMERCIAL: 'cyan',
  TECHNICAL: 'grape',
  FINANCE: 'warning',
  BILLING: 'neutral',
  EXECUTIVE: 'flamingo',
};

const ACTIVITY_TONE: Record<ActivityType, BadgeTone> = {
  CALL: 'cyan',
  EMAIL: 'grape',
  MEETING: 'success',
  NOTE: 'neutral',
  DEMO: 'flamingo',
  OTHER: 'neutral',
};

const ACTIVITY_ICON: Record<ActivityType, string> = {
  CALL: '📞', EMAIL: '✉️', MEETING: '🤝', NOTE: '📝', DEMO: '🖥️', OTHER: '•',
};

const fmtDateTime = (s: string): string =>
  new Date(s).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
const fmtDate = (s: string): string =>
  new Date(s + 'T00:00:00').toLocaleDateString('en-US', { dateStyle: 'medium' });
const isOverdue = (d: string): boolean => new Date(d + 'T00:00:00') < new Date(new Date().toDateString());

// --------------------------------------------------------------------------- //
export default function CustomerDetail() {
  const { id = '' } = useParams();
  const qc = useQueryClient();

  const customerQuery = useQuery({
    queryKey: ['customer', id],
    queryFn: () => api.get<Customer>(`/v1/customers/${id}`),
    enabled: !!id,
  });
  const contactsQuery = useQuery({
    queryKey: ['contacts', id],
    queryFn: () => api.get<Contact[]>(`/v1/customers/${id}/contacts?limit=200`),
    enabled: !!id,
  });
  const activitiesQuery = useQuery({
    queryKey: ['activities', id],
    queryFn: () => api.get<Activity[]>(`/v1/customers/${id}/activities?limit=200`),
    enabled: !!id,
  });

  const [contactModal, setContactModal] = useState(false);
  const [activityModal, setActivityModal] = useState(false);

  if (customerQuery.isLoading) return <Spinner label="Loading customer…" />;
  if (customerQuery.isError) return <ErrorState error={customerQuery.error} />;
  const customer = customerQuery.data!;

  const contacts = contactsQuery.data ?? [];
  const activities = activitiesQuery.data ?? [];
  const nextFollowUp = activities
    .filter((a) => a.next_follow_up_date)
    .map((a) => a.next_follow_up_date!)
    .sort()[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link to="/customers" className="text-xs text-grape-soft hover:text-cyan">← Customers</Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <SectionHeader
            eyebrow="COMMERCIAL · CRM"
            title={customer.legal_name}
            description={customer.trading_name ?? undefined}
          />
          <div className="flex gap-2">
            <Badge tone="cyan">{customer.status}</Badge>
            <Badge tone="neutral">{customer.credit_status}</Badge>
            {customer.account_owner && <Badge tone="grape">Owner: {customer.account_owner}</Badge>}
          </div>
        </div>
      </div>

      {nextFollowUp && (
        <div className={`card flex items-center gap-3 ${isOverdue(nextFollowUp) ? 'border-flamingo/40' : 'border-cyan/30'}`}>
          <span className="text-xl">⏰</span>
          <div>
            <span className="label">Next follow-up</span>
            <div className={isOverdue(nextFollowUp) ? 'font-semibold text-flamingo' : 'font-semibold text-cyan'}>
              {fmtDate(nextFollowUp)} {isOverdue(nextFollowUp) ? '· OVERDUE' : ''}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Contacts */}
        <section className="lg:col-span-2 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg">Contacts</h2>
            <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setContactModal(true)}>+ Add</button>
          </div>
          {contactsQuery.isLoading ? (
            <Spinner />
          ) : contacts.length === 0 ? (
            <EmptyState title="No contacts" hint="Add the people you're engaging at this account." />
          ) : (
            <div className="flex flex-col gap-2">
              {contacts.map((c) => (
                <div key={c.id} className="card flex items-start justify-between gap-3 py-3">
                  <div>
                    <div className="font-medium text-white">{c.name}</div>
                    <div className="text-xs text-grape-soft">
                      {c.email ?? '—'}{c.phone ? ` · ${c.phone}` : ''}
                    </div>
                  </div>
                  <Badge tone={CONTACT_TONE[c.type]}>{c.type}</Badge>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Activity timeline */}
        <section className="lg:col-span-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg">Activity Timeline</h2>
            <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => setActivityModal(true)}>+ Log Activity</button>
          </div>
          {activitiesQuery.isLoading ? (
            <Spinner />
          ) : activities.length === 0 ? (
            <EmptyState title="No activity yet" hint="Log calls, emails, meetings and notes to control contact before a proposal." />
          ) : (
            <ol className="flex flex-col gap-3">
              {activities.map((a) => (
                <li key={a.id} className="card flex gap-3">
                  <div className="text-xl leading-none">{ACTIVITY_ICON[a.type]}</div>
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-white">{a.subject}</span>
                      <Badge tone={ACTIVITY_TONE[a.type]}>{a.type}</Badge>
                    </div>
                    <div className="text-xs text-grape-soft">{fmtDateTime(a.occurred_at)}</div>
                    {a.notes && <p className="mt-1 text-sm text-grape-soft">{a.notes}</p>}
                    {a.outcome && <p className="mt-1 text-sm text-white"><span className="text-grape-soft">Outcome:</span> {a.outcome}</p>}
                    {a.next_follow_up_date && (
                      <p className={`mt-1 text-xs ${isOverdue(a.next_follow_up_date) ? 'text-flamingo' : 'text-cyan'}`}>
                        Follow up: {fmtDate(a.next_follow_up_date)}{isOverdue(a.next_follow_up_date) ? ' (overdue)' : ''}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {contactModal && (
        <ContactModal
          customerId={id}
          onClose={() => setContactModal(false)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ['contacts', id] }); setContactModal(false); }}
        />
      )}
      {activityModal && (
        <ActivityModal
          customerId={id}
          contacts={contacts}
          onClose={() => setActivityModal(false)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ['activities', id] }); setActivityModal(false); }}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ContactModal({ customerId, onClose, onSaved }: { customerId: string; onClose: () => void; onSaved: () => void }) {
  const [type, setType] = useState<ContactType>('COMMERCIAL');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');

  const mut = useMutation({
    mutationFn: () =>
      api.post<Contact>(`/v1/customers/${customerId}/contacts`, {
        type, name, email: email || null, phone: phone || null,
      }),
    onSuccess: onSaved,
  });

  function submit(e: FormEvent) { e.preventDefault(); mut.mutate(); }

  return (
    <Modal open onClose={onClose} title="Add Contact">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="c_type">Type</label>
            <select id="c_type" className="input" value={type} onChange={(e) => setType(e.target.value as ContactType)}>
              {CONTACT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="c_name">Name</label>
            <input id="c_name" className="input" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="c_email">Email</label>
            <input id="c_email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="c_phone">Phone</label>
            <input id="c_phone" className="input" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
        </div>
        {mut.isError && <ErrorState error={mut.error} />}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={mut.isPending}>
            {mut.isPending ? 'Saving…' : 'Add Contact'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
function ActivityModal({
  customerId, contacts, onClose, onSaved,
}: { customerId: string; contacts: Contact[]; onClose: () => void; onSaved: () => void }) {
  const [type, setType] = useState<ActivityType>('CALL');
  const [subject, setSubject] = useState('');
  const [notes, setNotes] = useState('');
  const [outcome, setOutcome] = useState('');
  const [contactId, setContactId] = useState('');
  const [followUp, setFollowUp] = useState('');

  const mut = useMutation({
    mutationFn: () =>
      api.post<Activity>(`/v1/customers/${customerId}/activities`, {
        type,
        subject,
        notes: notes || null,
        outcome: outcome || null,
        contact_id: contactId || null,
        next_follow_up_date: followUp || null,
      }),
    onSuccess: onSaved,
  });

  function submit(e: FormEvent) { e.preventDefault(); mut.mutate(); }

  return (
    <Modal open onClose={onClose} title="Log Activity">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="a_type">Type</label>
            <select id="a_type" className="input" value={type} onChange={(e) => setType(e.target.value as ActivityType)}>
              {ACTIVITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="a_contact">Contact (optional)</label>
            <select id="a_contact" className="input" value={contactId} onChange={(e) => setContactId(e.target.value)}>
              <option value="">— none —</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.type})</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="a_subject">Subject</label>
          <input id="a_subject" className="input" required placeholder="Intro call — H200 demand"
            value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="a_notes">Notes</label>
          <textarea id="a_notes" className="input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="a_outcome">Outcome</label>
            <input id="a_outcome" className="input" placeholder="Positive; wants a quote"
              value={outcome} onChange={(e) => setOutcome(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="a_follow">Next Follow-up</label>
            <input id="a_follow" type="date" className="input" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
          </div>
        </div>
        {mut.isError && <ErrorState error={mut.error} />}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={mut.isPending}>
            {mut.isPending ? 'Saving…' : 'Log Activity'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
