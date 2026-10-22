// Economics & Commissions — TensorBay Commission Plan FY2026.
// One page with tabs: Dashboard, Reps, Deals (approval queue + margin guardrail),
// Commission Runs (quarterly), Costs. Reads need economics.read; writes need
// economics.write; deal approval needs commission.approve (Super Admin).
import { useMemo, useState, type FormEvent } from 'react';
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
  KpiCard,
  type BadgeTone,
  type Column,
} from '../components/ui';

// --------------------------------------------------------------------------- //
// Types (mirror backend schemas)
// --------------------------------------------------------------------------- //
type RepType = 'AE' | 'AM' | 'FINDER';
type RepStatus = 'ACTIVE' | 'INACTIVE';
type DealStatus = 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
type ArrType = 'NEW_LOGO' | 'EXPANSION' | 'RENEWAL';
type Component = 'AE' | 'AM' | 'FINDER';

interface Rep {
  id: string; name: string; email: string | null; type: RepType; status: RepStatus;
  base_salary: string | null; cognito_sub: string | null; payment_details: string | null; notes: string | null;
}
interface Deal {
  id: string; name: string; customer_id: string; opportunity_id: string | null; plan_id: string | null;
  arr_type: ArrType; arr: string; margin_pct: string; gross_profit: string;
  ae_id: string | null; am_id: string | null; is_referred: boolean; finder_id: string | null;
  booked_date: string; plan_year: number; status: DealStatus; margin_warning: boolean;
  approved_by: string | null; approved_at: string | null; rejection_reason: string | null; notes: string | null;
}
interface Statement {
  id: string; run_id: string; rep_id: string; component: Component; plan_year: number; quarter: number;
  ytd_arr: string; quota_arr: string; gate_cleared: boolean; rate: string; ytd_gross_profit: string;
  ytd_earned: string; prior_paid: string; amount: string; payment_status: 'UNPAID' | 'PAID';
  paid_at: string | null; payment_reference: string | null;
}
interface Run {
  id: string; plan_year: number; quarter: number; plan_id: string | null; status: 'DRAFT' | 'FINALIZED';
  total_commission: string; notes: string | null; statements?: Statement[];
}
interface CostItem {
  id: string; name: string; category: string; amount: string; currency: string; period: string;
  incurred_on: string | null; customer_id: string | null; deal_id: string | null; supplier_id: string | null; notes: string | null;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
const usd = (v: string | number | null | undefined) => {
  const n = typeof v === 'string' ? Number(v) : v ?? 0;
  return (n ?? 0).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};
const pct = (v: string | number | null | undefined) => {
  const n = typeof v === 'string' ? Number(v) : v ?? 0;
  return `${((n ?? 0) * 100).toFixed(1)}%`;
};

const DEAL_TONE: Record<DealStatus, BadgeTone> = {
  PENDING_APPROVAL: 'warning', APPROVED: 'success', REJECTED: 'flamingo', CANCELLED: 'neutral',
};
const REP_TONE: Record<RepType, BadgeTone> = { AE: 'cyan', AM: 'grape', FINDER: 'flamingo' };

const TABS = ['Dashboard', 'Reps', 'Deals', 'Commission Runs', 'Costs'] as const;
type Tab = (typeof TABS)[number];

export default function Economics() {
  const [tab, setTab] = useState<Tab>('Dashboard');
  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        eyebrow="SALES COMPENSATION · FY2026"
        title="Economics & Commissions"
        description="Gross-profit-share commissions (AE/AM 10%, finder 3%), annual ARR quota gates, quarterly runs, cost tracking and real margin."
      />
      <div className="flex flex-wrap gap-1 border-b border-white/10">
        {TABS.map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
              tab === t ? 'bg-white/10 text-white' : 'text-grape-soft hover:text-white'
            }`}>{t}</button>
        ))}
      </div>
      {tab === 'Dashboard' && <DashboardTab />}
      {tab === 'Reps' && <RepsTab />}
      {tab === 'Deals' && <DealsTab />}
      {tab === 'Commission Runs' && <RunsTab />}
      {tab === 'Costs' && <CostsTab />}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Dashboard tab
// --------------------------------------------------------------------------- //
function DashboardTab() {
  const year = new Date().getFullYear();
  const deals = useQuery({ queryKey: ['eco-deals'], queryFn: () => api.get<Deal[]>('/v1/economics/deals?limit=500') });
  const runs = useQuery({ queryKey: ['eco-runs'], queryFn: () => api.get<Run[]>('/v1/economics/runs?limit=500') });

  const approved = (deals.data ?? []).filter((d) => d.status === 'APPROVED');
  const pending = (deals.data ?? []).filter((d) => d.status === 'PENDING_APPROVAL');
  const warnings = pending.filter((d) => d.margin_warning);
  const totalArr = approved.reduce((s, d) => s + Number(d.arr), 0);
  const totalGp = approved.reduce((s, d) => s + Number(d.gross_profit), 0);
  const totalCommission = (runs.data ?? []).reduce((s, r) => s + Number(r.total_commission), 0);

  if (deals.isLoading || runs.isLoading) return <Spinner label="Loading economics…" />;
  if (deals.isError) return <ErrorState error={deals.error} />;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Approved ARR" value={usd(totalArr)} accent="cyan" sub={`${approved.length} deals`} />
        <KpiCard label="Gross profit (nominal)" value={usd(totalGp)} accent="grape" />
        <KpiCard label="Commission to date" value={usd(totalCommission)} accent="white" sub={`${(runs.data ?? []).length} runs`} />
        <KpiCard label="Pending approval" value={pending.length} accent="flamingo"
          sub={warnings.length ? `${warnings.length} below-margin ⚠` : 'none below margin'} />
      </div>
      {warnings.length > 0 && (
        <div className="card border-amber-400/30">
          <h3 className="mb-2 text-lg text-amber-300">⚠ Margin warnings awaiting approval</h3>
          <ul className="flex flex-col gap-1 text-sm text-grape-soft">
            {warnings.map((d) => (
              <li key={d.id}>{d.name} — <span className="text-amber-300">{pct(d.margin_pct)}</span> margin · {usd(d.arr)} ARR</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <h3 className="mb-3 text-lg">Latest commission runs</h3>
        <DataTable
          columns={[
            { key: 'period', header: 'Period', render: (r: Run) => `${r.plan_year} Q${r.quarter}` },
            { key: 'status', header: 'Status', render: (r: Run) => <Badge tone={r.status === 'FINALIZED' ? 'success' : 'warning'}>{r.status}</Badge> },
            { key: 'total', header: 'Total commission', className: 'text-right', render: (r: Run) => usd(r.total_commission) },
          ]}
          rows={(runs.data ?? []).slice(0, 8)}
          rowKey={(r) => r.id}
          empty={<EmptyState title="No runs yet" hint="Create a quarterly run in the Commission Runs tab." />}
        />
      </div>
      <p className="text-xs text-grape-soft/70">Plan year {year}. Figures reflect approved deals and calculated runs.</p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Reps tab
// --------------------------------------------------------------------------- //
const emptyRep = () => ({ name: '', email: '', type: 'AE' as RepType, status: 'ACTIVE' as RepStatus, base_salary: '', cognito_sub: '', payment_details: '', notes: '' });

function RepsTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('economics.write');
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyRep());

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['eco-reps'], queryFn: () => api.get<Rep[]>('/v1/economics/reps?limit=500'),
  });

  const reset = () => { setEditId(null); setForm(emptyRep()); };
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name, email: form.email || null, type: form.type, status: form.status,
        base_salary: form.base_salary ? form.base_salary : null,
        cognito_sub: form.cognito_sub || null, payment_details: form.payment_details || null, notes: form.notes || null,
      };
      return editId ? api.patch<Rep>(`/v1/economics/reps/${editId}`, payload) : api.post<Rep>('/v1/economics/reps', payload);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-reps'] }); toast.success(editId ? 'Rep updated' : 'Rep created'); setOpen(false); reset(); },
    onError: (e) => toast.error(errMessage(e, 'Could not save rep')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/economics/reps/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-reps'] }); toast.success('Rep deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete rep (may be referenced by deals — set INACTIVE instead)')),
  });

  function openEdit(r: Rep) {
    setEditId(r.id);
    setForm({ name: r.name, email: r.email ?? '', type: r.type, status: r.status, base_salary: r.base_salary ?? '', cognito_sub: r.cognito_sub ?? '', payment_details: r.payment_details ?? '', notes: r.notes ?? '' });
    setOpen(true);
  }

  const columns: Array<Column<Rep>> = [
    { key: 'name', header: 'Name', render: (r) => <div className="flex flex-col"><span className="font-medium text-white">{r.name}</span>{r.email && <span className="text-xs text-grape-soft">{r.email}</span>}</div> },
    { key: 'type', header: 'Role', render: (r) => <Badge tone={REP_TONE[r.type]}>{r.type}</Badge> },
    { key: 'status', header: 'Status', render: (r) => <Badge tone={r.status === 'ACTIVE' ? 'success' : 'neutral'}>{r.status}</Badge> },
    { key: 'base_salary', header: 'Base salary', className: 'text-right', render: (r) => r.base_salary ? usd(r.base_salary) : '—' },
    { key: 'portal', header: 'Portal', render: (r) => r.cognito_sub ? <Badge tone="cyan">linked</Badge> : <span className="text-grape-soft">—</span> },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (r) => canWrite ? (
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(r)}>Edit</button>
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo" onClick={() => { if (confirm(`Delete rep ${r.name}?`)) del.mutate(r.id); }}>Delete</button>
        </div>
      ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">{canWrite && <button type="button" className="btn-primary" onClick={() => { reset(); setOpen(true); }}>+ New Rep</button>}</div>
      {isLoading ? <Spinner label="Loading reps…" /> : isError ? <ErrorState error={error} /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(r) => r.id}
          empty={<EmptyState title="No reps yet" hint="Add Account Executives, Account Managers and finders." />} />
      )}
      <Modal open={open} onClose={() => { setOpen(false); reset(); }} title={editId ? 'Edit Rep' : 'New Rep'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div><label className="label">Name</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Role</label>
              <select className="input" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as RepType })}>
                <option value="AE">AE — Account Executive</option><option value="AM">AM — Account Manager</option><option value="FINDER">FINDER — Referral partner</option>
              </select></div>
            <div><label className="label">Status</label>
              <select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as RepStatus })}>
                <option value="ACTIVE">ACTIVE</option><option value="INACTIVE">INACTIVE</option>
              </select></div>
          </div>
          <div><label className="label">Email</label><input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Base salary (USD)</label><input className="input" type="number" min="0" value={form.base_salary} onChange={(e) => setForm({ ...form, base_salary: e.target.value })} /></div>
            <div><label className="label">Cognito sub (portal link)</label><input className="input" placeholder="optional" value={form.cognito_sub} onChange={(e) => setForm({ ...form, cognito_sub: e.target.value })} /></div>
          </div>
          <div><label className="label">Payment details</label><textarea className="input" rows={2} value={form.payment_details} onChange={(e) => setForm({ ...form, payment_details: e.target.value })} /></div>
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); reset(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : editId ? 'Save' : 'Create'}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Deals tab (approval queue + margin guardrail)
// --------------------------------------------------------------------------- //
const emptyDeal = () => ({ name: '', customer_id: '', arr: '', margin_pct: '', arr_type: 'NEW_LOGO' as ArrType, ae_id: '', am_id: '', is_referred: false, finder_id: '', booked_date: new Date().toISOString().slice(0, 10), notes: '' });

function DealsTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('economics.write');
  const canApprove = hasPermission('commission.approve');
  const [statusFilter, setStatusFilter] = useState<DealStatus | ''>('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyDeal());

  const reps = useQuery({ queryKey: ['eco-reps'], queryFn: () => api.get<Rep[]>('/v1/economics/reps?limit=500') });
  const repName = useMemo(() => Object.fromEntries((reps.data ?? []).map((r) => [r.id, r.name])), [reps.data]);
  const deals = useQuery({
    queryKey: ['eco-deals', statusFilter],
    queryFn: () => api.get<Deal[]>(`/v1/economics/deals?limit=500${statusFilter ? `&status=${statusFilter}` : ''}`),
  });

  const save = useMutation({
    mutationFn: () => api.post<Deal>('/v1/economics/deals', {
      name: form.name, customer_id: form.customer_id, arr: form.arr,
      margin_pct: form.margin_pct ? form.margin_pct : null, arr_type: form.arr_type,
      ae_id: form.ae_id || null, am_id: form.am_id || null,
      is_referred: form.is_referred, finder_id: form.is_referred ? (form.finder_id || null) : null,
      booked_date: form.booked_date, notes: form.notes || null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-deals'] }); toast.success('Deal created (pending approval)'); setOpen(false); setForm(emptyDeal()); },
    onError: (e) => toast.error(errMessage(e, 'Could not create deal')),
  });
  const approve = useMutation({
    mutationFn: ({ id, ack }: { id: string; ack: boolean }) => api.post<Deal>(`/v1/economics/deals/${id}/approve`, { acknowledge_margin_warning: ack }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-deals'] }); toast.success('Deal approved'); },
    onError: (e) => toast.error(errMessage(e, 'Could not approve deal')),
  });
  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.post<Deal>(`/v1/economics/deals/${id}/reject`, { reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-deals'] }); toast.success('Deal rejected'); },
    onError: (e) => toast.error(errMessage(e, 'Could not reject deal')),
  });

  function doApprove(d: Deal) {
    if (d.margin_warning) {
      if (!confirm(`⚠ ${d.name} margin is ${pct(d.margin_pct)}, below the 30% default. Approve anyway? The AM and Super Admin will be emailed.`)) return;
      approve.mutate({ id: d.id, ack: true });
    } else {
      approve.mutate({ id: d.id, ack: false });
    }
  }
  function doReject(d: Deal) {
    const reason = prompt(`Reject ${d.name}? Reason:`);
    if (reason) reject.mutate({ id: d.id, reason });
  }

  const columns: Array<Column<Deal>> = [
    { key: 'name', header: 'Deal', render: (d) => <div className="flex flex-col"><span className="font-medium text-white">{d.name}</span><span className="text-xs text-grape-soft">{d.customer_id} · {d.arr_type}</span></div> },
    { key: 'arr', header: 'ARR', className: 'text-right', render: (d) => usd(d.arr) },
    { key: 'margin', header: 'Margin', className: 'text-right', render: (d) => <span className={d.margin_warning ? 'text-amber-300' : ''}>{pct(d.margin_pct)}{d.margin_warning ? ' ⚠' : ''}</span> },
    { key: 'gp', header: 'Gross profit', className: 'text-right', render: (d) => usd(d.gross_profit) },
    { key: 'reps', header: 'AE / AM / Finder', render: (d) => <span className="text-xs text-grape-soft">{[d.ae_id && `AE:${repName[d.ae_id] ?? '—'}`, d.am_id && `AM:${repName[d.am_id] ?? '—'}`, d.is_referred && d.finder_id && `F:${repName[d.finder_id] ?? '—'}`].filter(Boolean).join(' · ') || '—'}</span> },
    { key: 'status', header: 'Status', render: (d) => <Badge tone={DEAL_TONE[d.status]}>{d.status.replace('_', ' ')}</Badge> },
    {
      key: 'actions', header: '', className: 'text-right',
      render: (d) => d.status === 'PENDING_APPROVAL' && canApprove ? (
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-emerald-300" onClick={() => doApprove(d)}>Approve</button>
          <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo" onClick={() => doReject(d)}>Reject</button>
        </div>
      ) : null,
    },
  ];

  const aes = (reps.data ?? []).filter((r) => r.type === 'AE');
  const ams = (reps.data ?? []).filter((r) => r.type === 'AM');
  const finders = (reps.data ?? []).filter((r) => r.type === 'FINDER');

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select className="input max-w-xs" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as DealStatus | '')}>
          <option value="">All statuses</option>
          <option value="PENDING_APPROVAL">Pending approval</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
        </select>
        {canWrite && <button type="button" className="btn-primary" onClick={() => { setForm(emptyDeal()); setOpen(true); }}>+ New Deal</button>}
      </div>
      {deals.isLoading ? <Spinner label="Loading deals…" /> : deals.isError ? <ErrorState error={deals.error} /> : (
        <DataTable columns={columns} rows={deals.data ?? []} rowKey={(d) => d.id}
          empty={<EmptyState title="No deals" hint="Create a commissionable deal from a won opportunity." />} />
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="New Commission Deal">
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div><label className="label">Deal name</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Customer ID</label><input className="input" required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} /></div>
            <div><label className="label">ARR type</label>
              <select className="input" value={form.arr_type} onChange={(e) => setForm({ ...form, arr_type: e.target.value as ArrType })}>
                <option value="NEW_LOGO">New logo</option><option value="EXPANSION">Expansion</option><option value="RENEWAL">Renewal</option>
              </select></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">ARR (USD)</label><input className="input" type="number" min="0" required value={form.arr} onChange={(e) => setForm({ ...form, arr: e.target.value })} /></div>
            <div><label className="label">Margin (0–1, blank = plan default)</label><input className="input" type="number" step="0.01" min="0" max="1" placeholder="0.30" value={form.margin_pct} onChange={(e) => setForm({ ...form, margin_pct: e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Account Executive</label>
              <select className="input" value={form.ae_id} onChange={(e) => setForm({ ...form, ae_id: e.target.value })}>
                <option value="">—</option>{aes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
            <div><label className="label">Account Manager</label>
              <select className="input" value={form.am_id} onChange={(e) => setForm({ ...form, am_id: e.target.value })}>
                <option value="">—</option>{ams.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
          </div>
          <div className="flex items-center gap-3">
            <input id="referred" type="checkbox" checked={form.is_referred} onChange={(e) => setForm({ ...form, is_referred: e.target.checked })} />
            <label htmlFor="referred" className="text-sm text-grape-soft">Third-party referred (3% finder fee)</label>
          </div>
          {form.is_referred && (
            <div><label className="label">Finder</label>
              <select className="input" value={form.finder_id} onChange={(e) => setForm({ ...form, finder_id: e.target.value })}>
                <option value="">—</option>{finders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
          )}
          <div><label className="label">Booked date</label><input className="input" type="date" required value={form.booked_date} onChange={(e) => setForm({ ...form, booked_date: e.target.value })} /></div>
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Create (pending approval)'}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Commission Runs tab
// --------------------------------------------------------------------------- //
function RunsTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('economics.write');
  const canApprove = hasPermission('commission.approve');
  const [year, setYear] = useState(new Date().getFullYear());
  const [quarter, setQuarter] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const reps = useQuery({ queryKey: ['eco-reps'], queryFn: () => api.get<Rep[]>('/v1/economics/reps?limit=500') });
  const repName = useMemo(() => Object.fromEntries((reps.data ?? []).map((r) => [r.id, r.name])), [reps.data]);
  const runs = useQuery({ queryKey: ['eco-runs'], queryFn: () => api.get<Run[]>('/v1/economics/runs?limit=500') });
  const detail = useQuery({
    queryKey: ['eco-run', selected], enabled: !!selected,
    queryFn: () => api.get<Run>(`/v1/economics/runs/${selected}`),
  });

  const create = useMutation({
    mutationFn: () => api.post<Run>('/v1/economics/runs', { plan_year: year, quarter }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['eco-runs'] }); toast.success(`Run ${r.plan_year} Q${r.quarter} calculated`); setSelected(r.id); },
    onError: (e) => toast.error(errMessage(e, 'Could not create run')),
  });
  const finalize = useMutation({
    mutationFn: (id: string) => api.post<Run>(`/v1/economics/runs/${id}/finalize`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-runs'] }); qc.invalidateQueries({ queryKey: ['eco-run', selected] }); toast.success('Run finalized'); },
    onError: (e) => toast.error(errMessage(e, 'Could not finalize')),
  });
  const markPaid = useMutation({
    mutationFn: (sid: string) => api.post<Statement>(`/v1/economics/statements/${sid}/mark-paid`, { payment_reference: prompt('Payment reference (optional):') || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-run', selected] }); toast.success('Marked paid'); },
    onError: (e) => toast.error(errMessage(e, 'Could not mark paid')),
  });

  return (
    <div className="flex flex-col gap-4">
      {canWrite && (
        <div className="card flex flex-wrap items-end gap-3">
          <div><label className="label">Plan year</label><input className="input w-28" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></div>
          <div><label className="label">Quarter</label>
            <select className="input w-24" value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
              {[1, 2, 3, 4].map((q) => <option key={q} value={q}>Q{q}</option>)}
            </select></div>
          <button type="button" className="btn-primary" disabled={create.isPending} onClick={() => create.mutate()}>{create.isPending ? 'Calculating…' : 'Calculate run'}</button>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div>
          <h3 className="mb-2 text-sm text-grape-soft">Runs</h3>
          {runs.isLoading ? <Spinner /> : (
            <ul className="flex flex-col gap-1">
              {(runs.data ?? []).map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => setSelected(r.id)}
                    className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm transition ${selected === r.id ? 'border-cyan/40 bg-white/10' : 'border-white/5 bg-white/5 hover:bg-white/10'}`}>
                    <span className="text-white">{r.plan_year} Q{r.quarter}</span>
                    <span className="flex items-center gap-2"><span className="text-grape-soft">{usd(r.total_commission)}</span><Badge tone={r.status === 'FINALIZED' ? 'success' : 'warning'}>{r.status}</Badge></span>
                  </button>
                </li>
              ))}
              {(runs.data ?? []).length === 0 && <EmptyState title="No runs" hint="Calculate a quarterly run above." />}
            </ul>
          )}
        </div>
        <div>
          {!selected ? <EmptyState title="Select a run" hint="Pick a run to see per-rep statements." /> : detail.isLoading ? <Spinner /> : detail.data ? (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="text-lg">{detail.data.plan_year} Q{detail.data.quarter} · {usd(detail.data.total_commission)}</h3>
                {canApprove && detail.data.status === 'DRAFT' && (
                  <button type="button" className="btn-primary" onClick={() => finalize.mutate(detail.data!.id)}>Finalize</button>
                )}
              </div>
              <DataTable
                columns={[
                  { key: 'rep', header: 'Rep', render: (s: Statement) => <span className="text-white">{repName[s.rep_id] ?? s.rep_id}</span> },
                  { key: 'component', header: 'Pool', render: (s: Statement) => <Badge tone={REP_TONE[s.component]}>{s.component}</Badge> },
                  { key: 'ytd_arr', header: 'YTD ARR', className: 'text-right', render: (s: Statement) => usd(s.ytd_arr) },
                  { key: 'gate', header: 'Gate', render: (s: Statement) => <Badge tone={s.gate_cleared ? 'success' : 'neutral'}>{s.gate_cleared ? 'cleared' : `< ${usd(s.quota_arr)}`}</Badge> },
                  { key: 'ytd_earned', header: 'YTD earned', className: 'text-right', render: (s: Statement) => usd(s.ytd_earned) },
                  { key: 'amount', header: 'This quarter', className: 'text-right', render: (s: Statement) => <span className="font-medium text-white">{usd(s.amount)}</span> },
                  { key: 'pay', header: 'Payment', render: (s: Statement) => s.payment_status === 'PAID' ? <Badge tone="success">PAID</Badge> : (canWrite ? <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => markPaid.mutate(s.id)}>Mark paid</button> : <Badge tone="neutral">UNPAID</Badge>) },
                ]}
                rows={detail.data.statements ?? []}
                rowKey={(s) => s.id}
                empty={<EmptyState title="No statement lines" hint="No reps had qualifying approved deals this quarter." />}
              />
            </div>
          ) : <ErrorState error={detail.error} />}
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Costs tab
// --------------------------------------------------------------------------- //
const COST_CATEGORIES = ['GPU_ACQUISITION', 'COLOCATION', 'POWER', 'BANDWIDTH', 'STAFF', 'OTHER'];
const COST_PERIODS = ['ONE_TIME', 'MONTHLY', 'ANNUAL'];
const emptyCost = () => ({ name: '', category: 'GPU_ACQUISITION', amount: '', currency: 'USD', period: 'ONE_TIME', incurred_on: '', customer_id: '', deal_id: '', supplier_id: '', notes: '' });

function CostsTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('economics.write');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyCost());

  const { data, isLoading, isError, error } = useQuery({ queryKey: ['eco-costs'], queryFn: () => api.get<CostItem[]>('/v1/economics/costs?limit=500') });

  const save = useMutation({
    mutationFn: () => api.post<CostItem>('/v1/economics/costs', {
      name: form.name, category: form.category, amount: form.amount, currency: form.currency || 'USD', period: form.period,
      incurred_on: form.incurred_on || null, customer_id: form.customer_id || null, deal_id: form.deal_id || null,
      supplier_id: form.supplier_id || null, notes: form.notes || null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-costs'] }); toast.success('Cost added'); setOpen(false); setForm(emptyCost()); },
    onError: (e) => toast.error(errMessage(e, 'Could not add cost')),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/economics/costs/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['eco-costs'] }); toast.success('Cost deleted'); },
    onError: (e) => toast.error(errMessage(e, 'Could not delete cost')),
  });

  const total = (data ?? []).reduce((s, c) => s + Number(c.amount), 0);

  const columns: Array<Column<CostItem>> = [
    { key: 'name', header: 'Cost', render: (c) => <span className="font-medium text-white">{c.name}</span> },
    { key: 'category', header: 'Category', render: (c) => <Badge tone="grape">{c.category.replace('_', ' ')}</Badge> },
    { key: 'amount', header: 'Amount', className: 'text-right', render: (c) => usd(c.amount) },
    { key: 'period', header: 'Period', render: (c) => c.period.replace('_', ' ') },
    { key: 'alloc', header: 'Allocated to', render: (c) => <span className="text-xs text-grape-soft">{[c.customer_id && `cust:${c.customer_id}`, c.deal_id && 'deal'].filter(Boolean).join(' · ') || '—'}</span> },
    { key: 'actions', header: '', className: 'text-right', render: (c) => canWrite ? <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo" onClick={() => { if (confirm(`Delete cost ${c.name}?`)) del.mutate(c.id); }}>Delete</button> : null },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <KpiCard label="Total tracked cost" value={usd(total)} accent="flamingo" />
        {canWrite && <button type="button" className="btn-primary" onClick={() => { setForm(emptyCost()); setOpen(true); }}>+ New Cost</button>}
      </div>
      {isLoading ? <Spinner label="Loading costs…" /> : isError ? <ErrorState error={error} /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(c) => c.id}
          empty={<EmptyState title="No costs yet" hint="Track GPU acquisition and colocation costs here." />} />
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="New Cost">
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <div><label className="label">Name</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Category</label>
              <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {COST_CATEGORIES.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select></div>
            <div><label className="label">Period</label>
              <select className="input" value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })}>
                {COST_PERIODS.map((p) => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
              </select></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Amount (USD)</label><input className="input" type="number" min="0" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></div>
            <div><label className="label">Incurred on</label><input className="input" type="date" value={form.incurred_on} onChange={(e) => setForm({ ...form, incurred_on: e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Customer ID (optional)</label><input className="input" value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} /></div>
            <div><label className="label">Deal ID (optional)</label><input className="input" value={form.deal_id} onChange={(e) => setForm({ ...form, deal_id: e.target.value })} /></div>
          </div>
          <div><label className="label">Notes</label><textarea className="input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Add Cost'}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
