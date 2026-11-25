// Create / edit opportunity form, used on the Sales pipeline, on a customer and on a lead,
// so a deal can be opened wherever the person is working. The new deal appears on the
// pipeline board at the stage chosen here.
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { decodeClaims, getSession } from '../auth';
import { GPU_MODELS, COMMERCIAL_MODELS } from '../constants';
import {
  ESCROW_STAGES, MACRO_STAGES, STAGE_HINT, STAGE_LABEL, STAGE_PROBABILITY, type SalesStage,
} from '../salesStages';
import { Badge, ErrorState, Modal, Spinner, type BadgeTone } from './ui';
import { useToast, errMessage } from './toast';

type AvailabilityStatus = 'AVAILABLE' | 'PARTIALLY_AVAILABLE' | 'UNAVAILABLE';

const AVAIL_TONE: Record<AvailabilityStatus, BadgeTone> = {
  AVAILABLE: 'success',
  PARTIALLY_AVAILABLE: 'warning',
  UNAVAILABLE: 'flamingo',
};

const num = (v: number): string => v.toLocaleString('en-US');

/** Signed-in user's identity, for pre-filling the account-owner field. */
function currentUserOwner(): { name: string | null; email: string | null; sub: string | null } {
  const session = getSession();
  if (!session?.idToken) return { name: null, email: null, sub: null };
  try {
    const claims = decodeClaims(session.idToken);
    return {
      name: claims.name ?? claims.email ?? null,
      email: claims.email ?? null,
      sub: claims.sub ?? null,
    };
  } catch {
    return { name: null, email: null, sub: null };
  }
}

export interface Opportunity {
  id: string;
  customer_id: string;
  short_name: string | null;
  created_at: string;
  gpu_model: string;
  sku_id: string | null;
  quantity: number;
  expected_start: string | null;
  duration_months: number;
  commercial_model: string;
  expected_mrr: string | number;
  probability: number;
  sales_stage: SalesStage;
  account_owner: string | null;
  account_owner_email: string | null;
  account_owner_sub: string | null;
  region: string | null;
  assigned_to: string | null;
  next_action: string | null;
  escrow_required: boolean;
  upfront_pct: string | number | null;
  payment_structure: string | null;
  first_delivery_date: string | null;
  latest_delivery_date: string | null;
}

export interface OpportunityInput {
  customer_id: string;
  short_name: string;
  gpu_model: string;
  quantity: number;
  expected_start: string | null;
  duration_months: number;
  commercial_model: string;
  expected_mrr: number;
  probability: number;
  sales_stage: SalesStage;
  account_owner: string | null;
  account_owner_email: string | null;
  account_owner_sub: string | null;
  region: string;
  assigned_to: string;
  next_action: string;
  escrow_required: boolean;
  upfront_pct: string;
  payment_structure: string;
  first_delivery_date: string | null;
  latest_delivery_date: string | null;
}

interface CapacityCheck {
  gpu_model: string;
  requested: number;
  available: number;
  gap: number;
  incoming: number;
  status: AvailabilityStatus;
}

const today = (): string => new Date().toISOString().slice(0, 10);

/** Mirrors drive.service.opportunity_folder_name: YYYY-MM-<short name> (creation month). */
export function driveFolder(createdAt: string | undefined, shortName: string, gpuModel: string, qty: number): string {
  const d = createdAt ? new Date(createdAt) : new Date();
  const label = shortName.trim() || `${gpuModel}-${qty}`;
  const ym = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
  return `${ym}-${label.replace(/\s*[\\/]+\s*/g, ' - ').replace(/\s+/g, ' ')}`;
}

/** Default win probability for a stage; ON_HOLD has none (a hold keeps the current one). */
export const stageProb = (s: SalesStage, current = 0): number => (s === 'ON_HOLD' ? current : STAGE_PROBABILITY[s]);

export function emptyOpportunity(stage: SalesStage = 'NEW_LEAD'): OpportunityInput {
  return {
    customer_id: '',
    short_name: '',
    gpu_model: 'H200',
    quantity: 8,
    expected_start: today(),
    duration_months: 12,
    commercial_model: 'GPU_MONTHLY',
    expected_mrr: 0,
    probability: stageProb(stage),
    sales_stage: stage,
    account_owner: currentUserOwner().name,
    account_owner_email: currentUserOwner().email,
    account_owner_sub: currentUserOwner().sub,
    region: '',
    assigned_to: '',
    next_action: '',
    escrow_required: true,
    upfront_pct: '',
    payment_structure: '',
    first_delivery_date: null,
    latest_delivery_date: null,
  };
}


export interface OpportunityFormProps {
  open: boolean;
  onClose: () => void;
  /** Edit this opportunity; omit to create a new one. */
  editing?: Opportunity | null;
  /** Stage a new opportunity starts in (it appears in that column of the board). */
  stage?: SalesStage;
  /** Create for this customer: the customer field is filled in and locked. */
  customerId?: string;
  /** Pre-filled values for a new opportunity (e.g. from a lead). */
  defaults?: Partial<OpportunityInput>;
  onSaved?: (opportunity: Opportunity) => void;
}

interface CustomerLite { id: string; legal_name: string }

export default function OpportunityFormModal({
  open, onClose, editing = null, stage = 'NEW_LEAD', customerId, defaults, onSaved,
}: OpportunityFormProps) {
  const qc = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<OpportunityInput>(() => emptyOpportunity(stage));
  const lockCustomer = !!customerId && !editing;

  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
    enabled: open,
  });

  // Fill the form each time it opens.
  useEffect(() => {
    if (!open) return;
    if (editing) {
      setForm({
        customer_id: editing.customer_id,
        short_name: editing.short_name ?? '',
        gpu_model: editing.gpu_model,
        quantity: editing.quantity,
        expected_start: editing.expected_start,
        duration_months: editing.duration_months,
        commercial_model: editing.commercial_model,
        expected_mrr: Number(editing.expected_mrr),
        probability: editing.probability,
        sales_stage: editing.sales_stage,
        account_owner: editing.account_owner,
        account_owner_email: editing.account_owner_email,
        account_owner_sub: editing.account_owner_sub,
        region: editing.region ?? '',
        assigned_to: editing.assigned_to ?? '',
        next_action: editing.next_action ?? '',
        escrow_required: editing.escrow_required ?? true,
        upfront_pct: editing.upfront_pct === null || editing.upfront_pct === undefined ? '' : String(Number(editing.upfront_pct)),
        payment_structure: editing.payment_structure ?? '',
        first_delivery_date: editing.first_delivery_date ?? null,
        latest_delivery_date: editing.latest_delivery_date ?? null,
      });
    } else {
      setForm({ ...emptyOpportunity(stage), ...defaults, customer_id: customerId ?? defaults?.customer_id ?? '' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing?.id]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['opportunities'] });
    qc.invalidateQueries({ queryKey: ['inventory-lanes'] });
  };

  const createMut = useMutation({
    mutationFn: (payload: OpportunityInput) => api.post<Opportunity>('/v1/sales/opportunities', payload),
    onSuccess: (o) => {
      invalidate();
      toast.success('Opportunity created. It is on the pipeline board.');
      onSaved?.(o);
      onClose();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not create opportunity')),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<OpportunityInput> }) =>
      api.patch<Opportunity>(`/v1/sales/opportunities/${id}`, payload),
    onSuccess: (o) => {
      invalidate();
      toast.success('Opportunity updated');
      onSaved?.(o);
      onClose();
    },
    onError: (e) => toast.error(errMessage(e, 'Could not update opportunity')),
  });

  function submitOpp(e: FormEvent) {
    e.preventDefault();
    // An empty short name is stored as "none" (the folder then uses <model>-<qty>).
    const blank = (v: string) => (v.trim() || null) as unknown as string;
    const payload = {
      ...form, short_name: blank(form.short_name), region: blank(form.region), assigned_to: blank(form.assigned_to), next_action: blank(form.next_action),
      upfront_pct: (form.upfront_pct.trim() === '' ? null : Number(form.upfront_pct)) as unknown as string,
      payment_structure: blank(form.payment_structure),
    };
    if (editing) updateMut.mutate({ id: editing.id, payload });
    else createMut.mutate(payload);
  }

  const isServerModel = form.commercial_model.includes('SERVER');

  return (
      <Modal open={open} onClose={onClose} size="wide" title={editing ? 'Edit Opportunity' : 'New Opportunity'}>
        <form className="flex flex-col gap-5" onSubmit={submitOpp}>
          <div className="grid grid-cols-1 gap-x-8 gap-y-4 lg:grid-cols-2">
            {/* Left: what is being sold */}
            <div className="flex min-w-0 flex-col gap-4">
              <span className="eyebrow">THE DEAL</span>
          <div>
            <label className="label" htmlFor="opp_customer">Customer</label>
            <select
              id="opp_customer"
              className="input"
              required
              disabled={lockCustomer}
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
            <label className="label" htmlFor="opp_short">Short name</label>
            <input id="opp_short" className="input" maxLength={60} placeholder="e.g. Foxgaroo GB200"
              value={form.short_name} onChange={(e) => setForm({ ...form, short_name: e.target.value })} />
            <p className="mt-1 text-xs text-grape-soft" data-testid="opp-folder-preview">
              Drive folder: <span className="text-white">{driveFolder(editing?.created_at, form.short_name, form.gpu_model, form.quantity)}</span>
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_model">{isServerModel ? 'Server / GPU Model' : 'GPU Model'}</label>
              <input
                id="opp_model"
                className="input"
                required
                list="gpu-model-options"
                placeholder={isServerModel ? 'SERVER-8X-H200' : 'H200'}
                value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })}
              />
              <datalist id="gpu-model-options">
                {GPU_MODELS.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="label" htmlFor="opp_qty">Quantity ({isServerModel ? 'servers' : 'GPUs'})</label>
              <input
                id="opp_qty" type="number" min={1} className="input" required
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_cm">Commercial Model</label>
              <select
                id="opp_cm" className="input" required
                value={form.commercial_model}
                onChange={(e) => setForm({ ...form, commercial_model: e.target.value })}
              >
                {COMMERCIAL_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="opp_term">Duration (months)</label>
              <input
                id="opp_term" type="number" min={1} className="input" required
                value={form.duration_months}
                onChange={(e) => setForm({ ...form, duration_months: Number(e.target.value) })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_mrr">Expected MRR (USD)</label>
              <input
                id="opp_mrr" type="number" min={0} step="0.01" className="input" required
                value={form.expected_mrr}
                onChange={(e) => setForm({ ...form, expected_mrr: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_prob">Probability (%)</label>
              <input
                id="opp_prob" type="number" min={0} max={100} className="input" required
                value={form.probability}
                onChange={(e) => setForm({ ...form, probability: Number(e.target.value) })}
              />
            </div>
          </div>

              {/* Capacity check gate */}
              <CapacityCheckPanel gpuModel={form.gpu_model} quantity={form.quantity} />
            </div>

            {/* Right: where it is in the pipeline and who owns it */}
            <div className="flex min-w-0 flex-col gap-4">
              <span className="eyebrow">PIPELINE &amp; OWNERSHIP</span>
            <div>
              <label className="label" htmlFor="opp_stage">Stage</label>
              <select
                id="opp_stage" className="input" required
                value={form.sales_stage}
                onChange={(e) => {
                  // Picking a stage also proposes its default probability (still editable).
                  const st = e.target.value as SalesStage;
                  setForm({ ...form, sales_stage: st, probability: stageProb(st, form.probability) });
                }}
              >
                {MACRO_STAGES.map((m) => (
                  <optgroup key={m.key} label={`${m.n}. ${m.label}`}>
                    {m.stages.map((s) => (
                      <option key={s} value={s} title={STAGE_HINT[s]} disabled={!form.escrow_required && ESCROW_STAGES.includes(s)}>{STAGE_LABEL[s]}</option>
                    ))}
                  </optgroup>
                ))}
                <option value="ON_HOLD" title={STAGE_HINT.ON_HOLD}>On Hold</option>
                <option value="LOST" title={STAGE_HINT.LOST}>Lost</option>
              </select>
            </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_start">Expected Start</label>
              <input
                id="opp_start" type="date" className="input"
                value={form.expected_start ?? ''}
                onChange={(e) => setForm({ ...form, expected_start: e.target.value || null })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_owner">Account Owner</label>
              <OwnerAutocomplete
                value={form.account_owner ?? ''}
                email={form.account_owner_email}
                onChange={(name, email, sub) =>
                  setForm({
                    ...form,
                    account_owner: name || null,
                    account_owner_email: email,
                    account_owner_sub: sub,
                  })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_region">Region</label>
              <input
                id="opp_region" className="input" maxLength={64} placeholder="Brazil (São Paulo)"
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
              />
            </div>
            <div>
              <label className="label" htmlFor="opp_assigned">Assigned to (person)</label>
              <input
                id="opp_assigned" className="input" maxLength={255} placeholder="Who is responsible now"
                value={form.assigned_to}
                onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="opp_next">Next action</label>
            <input
              id="opp_next" className="input" maxLength={255} placeholder="Review MSA & Order Form"
              value={form.next_action}
              onChange={(e) => setForm({ ...form, next_action: e.target.value })}
            />
          </div>
          <label className="flex items-start gap-2 text-sm text-white">
            <input
              type="checkbox" id="opp_escrow" className="mt-1"
              checked={form.escrow_required}
              onChange={(e) => setForm({ ...form, escrow_required: e.target.checked })}
            />
            <span>
              The Upfront Payment goes through escrow
              <span className="block text-xs text-grape-soft">
                Required when the latest delivery target is after the 30th Business Day from the Order Effective Date (MSA 6.2).
                Turn off for a direct wire; the Payment substages are then skipped.
              </span>
            </span>
          </label>

          <span className="eyebrow mt-2">DELIVERY &amp; PAYMENT (ORDER FORM)</span>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="opp_first_delivery">First delivery target</label>
              <input id="opp_first_delivery" type="date" className="input"
                value={form.first_delivery_date ?? ''}
                onChange={(e) => setForm({ ...form, first_delivery_date: e.target.value || null })} />
            </div>
            <div>
              <label className="label" htmlFor="opp_latest_delivery">Latest delivery target (all capacity)</label>
              <input id="opp_latest_delivery" type="date" className="input"
                value={form.latest_delivery_date ?? ''}
                onChange={(e) => setForm({ ...form, latest_delivery_date: e.target.value || null })} />
            </div>
            <div>
              <label className="label" htmlFor="opp_upfront">Upfront Payment (% of Committed Value)</label>
              <input id="opp_upfront" type="number" min={0.01} max={99.99} step="0.01" className="input"
                placeholder="e.g. 30"
                value={form.upfront_pct}
                onChange={(e) => setForm({ ...form, upfront_pct: e.target.value })} />
              <p className="mt-1 text-xs text-grape-soft">Greater than 0% and less than 100%. No default.</p>
            </div>
            <div>
              <label className="label" htmlFor="opp_pay_structure">Payment structure (balance)</label>
              <select id="opp_pay_structure" className="input" value={form.payment_structure}
                onChange={(e) => setForm({ ...form, payment_structure: e.target.value })}>
                <option value="">Not decided</option>
                <option value="A">A. Monthly installments</option>
                <option value="B">B. Quarterly installments + deposit</option>
                <option value="C">C. Monthly installments + Security</option>
                <option value="D">D. Other balance schedule</option>
              </select>
            </div>
          </div>

            </div>
          </div>

          {(createMut.isError || updateMut.isError) && (
            <ErrorState error={createMut.error ?? updateMut.error} />
          )}

          {/* Stays in view while the form scrolls */}
          <div className="sticky bottom-0 -mb-1 flex justify-end gap-3 border-t border-white/10 bg-space-700 py-3">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              {createMut.isPending || updateMut.isPending
                ? 'Saving…'
                : editing ? 'Save Changes' : 'Create Opportunity'}
            </button>
          </div>
        </form>
      </Modal>

  );
}

// --------------------------------------------------------------------------- //
// --------------------------------------------------------------------------- //
// Capacity Check panel — the gate before quoting (plan §9)
// --------------------------------------------------------------------------- //
function CapacityCheckPanel({ gpuModel, quantity }: { gpuModel: string; quantity: number }) {
  const [checkKey, setCheckKey] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ['capacity-check', checkKey],
    queryFn: () =>
      api.get<CapacityCheck>(
        `/v1/capacity/check?gpu_model=${encodeURIComponent(gpuModel)}&quantity=${quantity}`,
      ),
    enabled: checkKey !== null,
  });

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="eyebrow">Capacity Check</span>
          <p className="text-xs text-grape-soft">Verify availability before quoting.</p>
        </div>
        <button
          type="button"
          className="btn-ghost text-sm"
          disabled={!gpuModel || quantity < 1}
          onClick={() => setCheckKey(`${gpuModel}:${quantity}:${Date.now()}`)}
        >
          Check {num(quantity)} × {gpuModel || '—'}
        </button>
      </div>

      {q.isFetching ? (
        <Spinner label="Checking capacity…" />
      ) : q.isError ? (
        <ErrorState error={q.error} />
      ) : q.data ? (
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <Badge tone={AVAIL_TONE[q.data.status]}>{q.data.status.replace('_', ' ')}</Badge>
          <span className="text-grape-soft">Requested <b className="text-white">{num(q.data.requested)}</b></span>
          <span className="text-grape-soft">Available <b className="text-white">{num(q.data.available)}</b></span>
          <span className="text-grape-soft">Incoming <b className="text-white">{num(q.data.incoming)}</b></span>
          {q.data.gap > 0 && <span className="text-flamingo">Gap <b>{num(q.data.gap)}</b></span>}
        </div>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// OwnerAutocomplete — free-text account-owner field with a real-time directory
// dropdown. Typing keeps the free text as the name (and clears email/sub, since
// it's no longer a verified directory match); picking a suggestion stores the
// full {name, email, sub}. Backed by GET /v1/directory/users?q=.
// --------------------------------------------------------------------------- //
interface DirectoryUser {
  sub: string;
  email: string | null;
  name: string | null;
}

function OwnerAutocomplete({
  value,
  email,
  onChange,
}: {
  value: string;
  email: string | null;
  onChange: (name: string, email: string | null, sub: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [debounced, setDebounced] = useState(value);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounce the typed value before querying the directory.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value.trim()), 200);
    return () => clearTimeout(t);
  }, [value]);

  // Close the dropdown on outside click.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = useQuery({
    queryKey: ['directory', 'users', debounced],
    queryFn: () =>
      api.get<DirectoryUser[]>(
        `/v1/directory/users${debounced ? `?q=${encodeURIComponent(debounced)}` : ''}`,
      ),
    enabled: open,
    staleTime: 60_000,
  });

  const results = q.data ?? [];

  return (
    <div ref={boxRef} className="relative">
      <input
        id="opp_owner"
        className="input"
        placeholder="Type a name — suggestions from your directory"
        autoComplete="off"
        value={value}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          // Free text: keep the typed name, drop the verified email/sub.
          onChange(e.target.value, null, null);
          setOpen(true);
        }}
      />
      {/* Show the verified email when the current value came from a directory pick. */}
      {email && (
        <p className="mt-1 text-xs text-cyan">✓ {email}</p>
      )}
      {open && (
        <div className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-xl border border-white/10 bg-space-700 shadow-card">
          {q.isLoading ? (
            <div className="px-3 py-2 text-xs text-grape-soft">Searching…</div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-xs text-grape-soft">
              No directory match — free text will be saved as-is.
            </div>
          ) : (
            results.map((u) => {
              const display = u.name ?? u.email ?? u.sub;
              return (
                <button
                  key={u.sub}
                  type="button"
                  className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition hover:bg-white/5"
                  onClick={() => {
                    onChange(display, u.email, u.sub);
                    setOpen(false);
                  }}
                >
                  <span className="text-sm text-white">{display}</span>
                  {u.email && u.email !== display && (
                    <span className="text-xs text-grape-soft">{u.email}</span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
