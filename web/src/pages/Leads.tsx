// Leads — inbound website pricing requests, routed to Account Managers by region.
// Work a lead (contacted / qualified), reassign (managers), disqualify, or convert
// it into a PROSPECT customer (+ optional opportunity). Reads need lead.read;
// changes need lead.write. Account Managers only see leads assigned to them.
import { useMemo, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { decodeClaims, getSession } from '../auth';
import { hasPermission } from '../permissions';
import { COMMERCIAL_MODELS } from '../constants';
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

type LeadStatus = 'NEW' | 'CONTACTED' | 'QUALIFIED' | 'CONVERTED' | 'DISQUALIFIED';

interface Lead {
  id: string;
  submission_id: string;
  source: string;
  name: string;
  email: string;
  company: string | null;
  sku_of_interest: string | null;
  gpu_count: number | null;
  pricing_model_or_term: string | null;
  site_language: string | null;
  region: string | null;
  country: string | null;
  message: string | null;
  page_url: string | null;
  submitted_at: string | null;
  status: LeadStatus;
  assigned_rep_id: string | null;
  needs_review: boolean;
  duplicate_of_id: string | null;
  disqualified_reason: string | null;
  notes: string | null;
  converted_customer_id: string | null;
  converted_opportunity_id: string | null;
  created_at: string;
}

interface Rep { id: string; name: string; type: 'AE' | 'AM' | 'FINDER'; status: 'ACTIVE' | 'INACTIVE'; lead_eligible: boolean }

interface ConvertResult {
  lead: Lead;
  customer_id: string;
  opportunity_id: string | null;
  customer_created: boolean;
}

const STATUS_TONE: Record<LeadStatus, BadgeTone> = {
  NEW: 'cyan', CONTACTED: 'grape', QUALIFIED: 'warning', CONVERTED: 'success', DISQUALIFIED: 'neutral',
};
const STATUSES: LeadStatus[] = ['NEW', 'CONTACTED', 'QUALIFIED', 'CONVERTED', 'DISQUALIFIED'];

// Mirrors the backend's "privileged" roles (can see all leads and reassign).
function isManager(): boolean {
  const session = getSession();
  if (!session?.idToken) return false;
  try {
    const groups = decodeClaims(session.idToken).groups ?? [];
    return groups.some((g) => g === 'SUPER_ADMIN' || g === 'SALES_MANAGER');
  } catch {
    return false;
  }
}

const place = (l: Lead) => [l.region, l.country].filter(Boolean).join(' · ') || '—';
const when = (iso: string) => new Date(iso).toLocaleString();

export default function Leads() {
  const qc = useQueryClient();
  const canWrite = hasPermission('lead.write');
  const manager = isManager();
  const [statusFilter, setStatusFilter] = useState<LeadStatus | ''>('');
  const [reviewOnly, setReviewOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const reps = useQuery({ queryKey: ['eco-reps'], queryFn: () => api.get<Rep[]>('/v1/economics/reps?limit=500') });
  const repName = useMemo(() => Object.fromEntries((reps.data ?? []).map((r) => [r.id, r.name])), [reps.data]);

  const leads = useQuery({
    queryKey: ['leads', statusFilter, reviewOnly, search],
    queryFn: () => {
      const p = new URLSearchParams({ limit: '200' });
      if (statusFilter) p.set('status', statusFilter);
      if (reviewOnly) p.set('needs_review', 'true');
      if (search.trim()) p.set('q', search.trim());
      return api.get<Lead[]>(`/v1/leads?${p.toString()}`);
    },
  });

  const open = (leads.data ?? []).find((l) => l.id === openId) ?? null;
  const refresh = () => qc.invalidateQueries({ queryKey: ['leads'] });

  const newCount = (leads.data ?? []).filter((l) => l.status === 'NEW').length;

  const columns: Array<Column<Lead>> = [
    { key: 'received', header: 'Received', render: (l) => <span className="text-xs text-grape-soft">{when(l.created_at)}</span> },
    {
      key: 'who', header: 'Lead',
      render: (l) => (
        <div className="flex flex-col">
          <span className="font-medium text-white">{l.name}</span>
          <span className="text-xs text-grape-soft">{l.company ? `${l.company} · ` : ''}{l.email}</span>
        </div>
      ),
    },
    {
      key: 'region', header: 'Region',
      render: (l) => (
        <div className="flex items-center gap-2">
          <span>{place(l)}</span>
          {l.needs_review && <Badge tone="warning">review</Badge>}
        </div>
      ),
    },
    {
      key: 'request', header: 'Request',
      render: (l) => (
        <span className="text-xs text-grape-soft">
          {[l.sku_of_interest, l.gpu_count ? `${l.gpu_count} GPUs` : null, l.pricing_model_or_term].filter(Boolean).join(' · ') || '—'}
        </span>
      ),
    },
    { key: 'am', header: 'Account Manager', render: (l) => (l.assigned_rep_id ? repName[l.assigned_rep_id] ?? '—' : <span className="text-flamingo">Unassigned</span>) },
    {
      key: 'status', header: 'Status',
      render: (l) => (
        <div className="flex items-center gap-2">
          <Badge tone={STATUS_TONE[l.status]}>{l.status}</Badge>
          {l.duplicate_of_id && <Badge tone="grape">repeat</Badge>}
        </div>
      ),
    },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (l) => <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setOpenId(l.id)}>Open</button>,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        eyebrow="SALES · INBOUND"
        title="Leads"
        description="Pricing requests from the website, routed to an Account Manager by region. Work them here, then convert qualified ones into a customer."
      />

      <div className="flex flex-wrap items-center gap-3">
        <SearchInput value={search} onChange={setSearch} placeholder="Search name, email, company…" />
        <select className="input max-w-[180px]" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as LeadStatus | '')}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-grape-soft">
          <input type="checkbox" checked={reviewOnly} onChange={(e) => setReviewOnly(e.target.checked)} />
          Needs review only
        </label>
        {newCount > 0 && <Badge tone="cyan">{newCount} new</Badge>}
        {canWrite && (
          <button type="button" className="btn-primary ml-auto" onClick={() => setCreating(true)}>
            + New lead
          </button>
        )}
      </div>

      {leads.isLoading ? (
        <Spinner label="Loading leads…" />
      ) : leads.isError ? (
        <ErrorState error={leads.error} />
      ) : (
        <DataTable
          columns={columns}
          rows={leads.data ?? []}
          rowKey={(l) => l.id}
          empty={<EmptyState title="No leads" hint="Website pricing requests appear here automatically. You can also add one with “New lead”." />}
        />
      )}

      {creating && (
        <NewLeadModal
          ams={(reps.data ?? []).filter((r) => r.lead_eligible && r.status === 'ACTIVE')}
          manager={manager}
          onClose={() => setCreating(false)}
          onCreated={(l) => { setCreating(false); refresh(); setOpenId(l.id); }}
        />
      )}

      {open && (
        <LeadModal
          lead={open}
          repName={repName}
          ams={(reps.data ?? []).filter((r) => r.lead_eligible && r.status === 'ACTIVE')}
          canWrite={canWrite}
          manager={manager}
          onClose={() => setOpenId(null)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="label">{label}</span>
      <span className="text-sm text-white">{children || <span className="text-grape-soft">—</span>}</span>
    </div>
  );
}

const LEAD_SOURCES = ['manual', 'phone', 'event', 'referral', 'linkedin', 'direct_email', 'other'];

function NewLeadModal({
  ams, manager, onClose, onCreated,
}: { ams: Rep[]; manager: boolean; onClose: () => void; onCreated: (l: Lead) => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: '', email: '', company: '', source: 'manual', region: '', country: '',
    sku_of_interest: '', gpu_count: '', pricing_model_or_term: '', message: '', assigned_rep_id: '',
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [k]: e.target.value });
  const orNull = (v: string) => (v.trim() ? v.trim() : null);

  const create = useMutation({
    mutationFn: () =>
      api.post<Lead>('/v1/leads', {
        name: form.name.trim(),
        email: form.email.trim(),
        company: orNull(form.company),
        source: form.source,
        region: orNull(form.region),
        country: orNull(form.country),
        sku_of_interest: orNull(form.sku_of_interest),
        gpu_count: form.gpu_count ? Number(form.gpu_count) : null,
        pricing_model_or_term: orNull(form.pricing_model_or_term),
        message: orNull(form.message),
        assigned_rep_id: manager && form.assigned_rep_id ? form.assigned_rep_id : null,
      }),
    onSuccess: (l) => { toast.success('Lead created'); onCreated(l); },
    onError: (e) => toast.error(errMessage(e, 'Could not create lead')),
  });

  return (
    <Modal open onClose={onClose} title="New lead">
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="nl_name">Name *</label>
            <input id="nl_name" className="input" required maxLength={255} value={form.name} onChange={set('name')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_email">Email *</label>
            <input id="nl_email" className="input" type="email" required value={form.email} onChange={set('email')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_company">Company</label>
            <input id="nl_company" className="input" maxLength={255} value={form.company} onChange={set('company')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_source">Source</label>
            <select id="nl_source" className="input" value={form.source} onChange={set('source')}>
              {LEAD_SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="nl_region">Region</label>
            <input id="nl_region" className="input" placeholder="e.g. North America" value={form.region} onChange={set('region')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_country">Country</label>
            <input id="nl_country" className="input" value={form.country} onChange={set('country')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_sku">SKU of interest</label>
            <input id="nl_sku" className="input" placeholder="e.g. H100" value={form.sku_of_interest} onChange={set('sku_of_interest')} />
          </div>
          <div>
            <label className="label" htmlFor="nl_gpus">GPU count</label>
            <input id="nl_gpus" className="input" type="number" min="1" value={form.gpu_count} onChange={set('gpu_count')} />
          </div>
          <div className="col-span-2">
            <label className="label" htmlFor="nl_term">Pricing model / term</label>
            <input id="nl_term" className="input" maxLength={255} value={form.pricing_model_or_term} onChange={set('pricing_model_or_term')} />
          </div>
          {manager && (
            <div className="col-span-2">
              <label className="label" htmlFor="nl_am">Account Manager</label>
              <select id="nl_am" className="input" value={form.assigned_rep_id} onChange={set('assigned_rep_id')}>
                <option value="">Auto-assign by region</option>
                {ams.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
          )}
          <div className="col-span-2">
            <label className="label" htmlFor="nl_msg">Notes / message</label>
            <textarea id="nl_msg" className="input" rows={3} maxLength={5000} value={form.message} onChange={set('message')} />
          </div>
        </div>
        {!manager && <p className="text-xs text-grape-soft">This lead will be assigned to you.</p>}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create lead'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function LeadModal({
  lead, repName, ams, canWrite, manager, onClose, onChanged,
}: {
  lead: Lead; repName: Record<string, string>; ams: Rep[]; canWrite: boolean; manager: boolean;
  onClose: () => void; onChanged: () => void;
}) {
  const toast = useToast();
  const navigate = useNavigate();
  const [notes, setNotes] = useState(lead.notes ?? '');
  const [converting, setConverting] = useState(false);
  const closed = lead.status === 'CONVERTED';

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<Lead>(`/v1/leads/${lead.id}`, body),
    onSuccess: () => { onChanged(); toast.success('Lead updated'); },
    onError: (e) => toast.error(errMessage(e, 'Could not update lead')),
  });
  const disqualify = useMutation({
    mutationFn: (reason: string) => api.post<Lead>(`/v1/leads/${lead.id}/disqualify`, { reason }),
    onSuccess: () => { onChanged(); toast.success('Lead disqualified'); },
    onError: (e) => toast.error(errMessage(e, 'Could not disqualify lead')),
  });

  function doDisqualify() {
    const reason = prompt('Reason for disqualifying this lead:');
    if (reason && reason.trim()) disqualify.mutate(reason.trim());
  }

  return (
    <>
      <Modal open onClose={onClose} title={`${lead.name}${lead.company ? ` · ${lead.company}` : ''}`}>
        <div className="flex max-h-[70vh] flex-col gap-4 overflow-y-auto pr-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[lead.status]}>{lead.status}</Badge>
            {lead.needs_review && <Badge tone="warning">needs review</Badge>}
            {lead.duplicate_of_id && <Badge tone="grape">repeat inquiry</Badge>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Email"><a className="text-cyan" href={`mailto:${lead.email}`}>{lead.email}</a></Field>
            <Field label="Region">{place(lead) === '—' ? '' : place(lead)}</Field>
            <Field label="SKU of interest">{lead.sku_of_interest}</Field>
            <Field label="GPU count">{lead.gpu_count}</Field>
            <Field label="Pricing model / term">{lead.pricing_model_or_term}</Field>
            <Field label="Site language">{lead.site_language}</Field>
            <Field label="Received">{when(lead.created_at)}</Field>
            <Field label="Account Manager">{lead.assigned_rep_id ? repName[lead.assigned_rep_id] : 'Unassigned'}</Field>
          </div>

          <div className="flex flex-col gap-1">
            <span className="label">Message</span>
            <p className="whitespace-pre-wrap rounded-xl border border-white/5 bg-white/5 p-3 text-sm text-white">
              {lead.message || <span className="text-grape-soft">No message.</span>}
            </p>
          </div>

          {lead.disqualified_reason && (
            <Field label="Disqualified because">{lead.disqualified_reason}</Field>
          )}
          {lead.converted_customer_id && (
            <div className="flex gap-3">
              <button type="button" className="btn-ghost" onClick={() => navigate(`/customers/${lead.converted_customer_id}`)}>Open customer →</button>
              {lead.converted_opportunity_id && (
                <button type="button" className="btn-ghost" onClick={() => navigate(`/opportunities/${lead.converted_opportunity_id}`)}>Open opportunity →</button>
              )}
            </div>
          )}

          {canWrite && !closed && (
            <>
              {manager && (
                <div>
                  <label className="label" htmlFor="lead_am">Reassign Account Manager</label>
                  <select id="lead_am" className="input" value={lead.assigned_rep_id ?? ''}
                    onChange={(e) => e.target.value && patch.mutate({ assigned_rep_id: e.target.value })}>
                    <option value="">{lead.assigned_rep_id ? '—' : 'Select…'}</option>
                    {ams.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="label" htmlFor="lead_notes">Notes</label>
                <textarea id="lead_notes" className="input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
                <div className="mt-2 flex justify-end">
                  <button type="button" className="btn-ghost px-3 py-1 text-xs" disabled={patch.isPending || notes === (lead.notes ?? '')}
                    onClick={() => patch.mutate({ notes })}>Save notes</button>
                </div>
              </div>
              <div className="flex flex-wrap justify-between gap-2 border-t border-white/5 pt-4">
                <div className="flex flex-wrap gap-2">
                  {lead.status === 'DISQUALIFIED' && (
                    <button type="button" className="btn-ghost" onClick={() => patch.mutate({ status: 'NEW' })}>Reopen</button>
                  )}
                  {lead.status === 'NEW' && (
                    <button type="button" className="btn-ghost" onClick={() => patch.mutate({ status: 'CONTACTED' })}>Mark contacted</button>
                  )}
                  {(lead.status === 'NEW' || lead.status === 'CONTACTED') && (
                    <button type="button" className="btn-ghost" onClick={() => patch.mutate({ status: 'QUALIFIED' })}>Mark qualified</button>
                  )}
                  {lead.status !== 'DISQUALIFIED' && (
                    <button type="button" className="btn-ghost text-flamingo" onClick={doDisqualify}>Disqualify</button>
                  )}
                </div>
                <button type="button" className="btn-primary" onClick={() => setConverting(true)}>Convert to customer</button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {converting && (
        <ConvertModal
          lead={lead}
          onClose={() => setConverting(false)}
          onDone={(r) => {
            setConverting(false);
            onChanged();
            toast.success(r.customer_created ? 'Customer created' : 'Added to existing customer');
            navigate(`/customers/${r.customer_id}`);
          }}
        />
      )}
    </>
  );
}

function ConvertModal({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: (r: ConvertResult) => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    customer_name: lead.company ?? lead.name,
    create_opportunity: false,
    gpu_model: lead.sku_of_interest ?? '',
    quantity: lead.gpu_count ? String(lead.gpu_count) : '',
    duration_months: '12',
    commercial_model: 'RESERVED',
    expected_mrr: '',
  });

  const convert = useMutation({
    mutationFn: () =>
      api.post<ConvertResult>(`/v1/leads/${lead.id}/convert`, {
        customer_name: form.customer_name || null,
        create_opportunity: form.create_opportunity,
        gpu_model: form.create_opportunity ? form.gpu_model || null : null,
        quantity: form.create_opportunity && form.quantity ? Number(form.quantity) : null,
        duration_months: form.create_opportunity && form.duration_months ? Number(form.duration_months) : null,
        commercial_model: form.create_opportunity ? form.commercial_model : null,
        expected_mrr: form.create_opportunity && form.expected_mrr ? form.expected_mrr : null,
      }),
    onSuccess: onDone,
    onError: (e) => toast.error(errMessage(e, 'Could not convert lead')),
  });

  return (
    <Modal open onClose={onClose} title="Convert to customer">
      <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); convert.mutate(); }}>
        <p className="text-sm text-grape-soft">
          Creates a PROSPECT customer (or adds {lead.name} to an existing one with the same name), a contact, and logs the
          website request as an email activity.
        </p>
        <div>
          <label className="label" htmlFor="cv_name">Customer name</label>
          <input id="cv_name" className="input" required value={form.customer_name}
            onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 text-sm text-white">
          <input type="checkbox" checked={form.create_opportunity}
            onChange={(e) => setForm({ ...form, create_opportunity: e.target.checked })} />
          Also create an opportunity
        </label>
        {form.create_opportunity && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="cv_gpu">GPU model</label>
              <input id="cv_gpu" className="input" required value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="cv_qty">Quantity</label>
              <input id="cv_qty" className="input" type="number" min="1" required value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="cv_term">Term (months)</label>
              <input id="cv_term" className="input" type="number" min="1" required value={form.duration_months}
                onChange={(e) => setForm({ ...form, duration_months: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="cv_model">Commercial model</label>
              <select id="cv_model" className="input" value={form.commercial_model}
                onChange={(e) => setForm({ ...form, commercial_model: e.target.value })}>
                {COMMERCIAL_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="label" htmlFor="cv_mrr">Expected MRR (USD)</label>
              <input id="cv_mrr" className="input" type="number" min="0" step="0.01" required value={form.expected_mrr}
                onChange={(e) => setForm({ ...form, expected_mrr: e.target.value })} />
            </div>
          </div>
        )}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={convert.isPending}>
            {convert.isPending ? 'Converting…' : 'Convert'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
