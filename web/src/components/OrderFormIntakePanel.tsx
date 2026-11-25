// Order Form data from the customer: create a private link, send it, see when the
// customer has filled it in. The commercial owner also gets an email at that moment.
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from './toast';
import { Badge, ErrorState, Spinner } from './ui';
import { fmtDateTime } from '../dates';

interface Intake {
  id: string;
  status: 'PENDING' | 'SUBMITTED' | 'REVOKED';
  expired: boolean;
  expires_at: string;
  submitted_at: string | null;
  created_at: string;
  data: Record<string, unknown> | null;
  token: string | null;
}

const FIELDS: Array<[string, string]> = [
  ['legal_name', 'Legal name'], ['company_form', 'Company form'], ['jurisdiction', 'Jurisdiction'],
  ['registration_number', 'Registration number'], ['registered_address', 'Registered address'], ['website', 'Website'],
  ['signatory_name', 'Signatory'], ['signatory_title', 'Title'], ['signatory_email', 'Signatory email'],
  ['notices_email', 'Notices email'],
  ['technical_contact_name', 'Technical contact'], ['technical_contact_email', 'Technical email'], ['technical_contact_phone', 'Technical phone'],
  ['billing_contact_name', 'Billing contact'], ['billing_contact_email', 'Billing email'], ['billing_contact_phone', 'Billing phone'],
  ['workload_description', 'Workload'], ['compute_fabric', 'Compute fabric'],
  ['shared_storage_tb', 'Shared storage (TB)'], ['dedicated_internet_gbps', 'Internet (Gb/s)'], ['monthly_egress_tb', 'Egress (TB/month)'],
  ['access_methods', 'Access'], ['allowed_ip_addresses', 'Allowed IPs'], ['os_image_notes', 'OS / software'],
  ['region_preference', 'Preferred region'], ['preferred_start_date', 'Preferred start'], ['additional_notes', 'Notes'],
];

const show = (v: unknown): string => (Array.isArray(v) ? v.join(', ') : v === null || v === undefined ? '' : String(v));
const linkFor = (token: string) => `${window.location.origin}/intake/${token}`;
const when = fmtDateTime;

export default function OrderFormIntakePanel({ opportunityId }: { opportunityId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = hasPermission('customer.write');
  const key = ['intake', opportunityId];
  const [showData, setShowData] = useState(false);

  const q = useQuery({ queryKey: key, queryFn: () => api.get<Intake[]>(`/v1/intake/opportunity/${opportunityId}`) });
  const refresh = () => qc.invalidateQueries({ queryKey: key });

  const create = useMutation({
    mutationFn: () => api.post<Intake>(`/v1/intake/opportunity/${opportunityId}/link`),
    onSuccess: () => { refresh(); toast.success('Link created. Copy it and send it to the customer.'); },
    onError: (e) => toast.error(errMessage(e, 'Could not create the link')),
  });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'reopen' | 'revoke' }) => api.post<Intake>(`/v1/intake/${id}/${action}`),
    onSuccess: (_d, { action }) => { refresh(); toast.success(action === 'reopen' ? 'Reopened: the customer can edit again' : 'Link revoked'); },
    onError: (e) => toast.error(errMessage(e, 'Action failed')),
  });

  async function copy(token: string) {
    try {
      await navigator.clipboard.writeText(linkFor(token));
      toast.success('Link copied');
    } catch {
      window.prompt('Copy this link:', linkFor(token));
    }
  }

  const rows = q.data ?? [];
  const submitted = rows.find((r) => r.status === 'SUBMITTED');
  const pending = rows.find((r) => r.status === 'PENDING');

  return (
    <section className="flex flex-col gap-3" data-testid="intake-panel">
      <span className="eyebrow">CUSTOMER DATA FOR THE ORDER FORM</span>
      <div className="card flex flex-col gap-3">
        <p className="text-xs text-grape-soft">
          Send the customer a private link to fill in their legal entity, signatory, contacts and technical needs.
          You get an email when they submit, and the MSA and other documents use these details.
        </p>

        {q.isLoading ? <Spinner label="Loading…" /> : q.isError ? <ErrorState error={q.error} /> : (
          <>
            {submitted && (
              <div className="flex flex-col gap-2" data-testid="intake-submitted">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="success">Received</Badge>
                  <span className="text-sm text-white">
                    {show(submitted.data?.legal_name)} filled in the form on {submitted.submitted_at ? when(submitted.submitted_at) : ''}.
                  </span>
                  <span className="text-sm text-cyan">The MSA can be generated.</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <a href="#documents" className="btn-primary px-3 py-1.5 text-sm">Generate documents ↓</a>
                  <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={() => setShowData(!showData)}>
                    {showData ? 'Hide' : 'View'} submitted data
                  </button>
                  {canWrite && !pending && (
                    <button type="button" className="btn-ghost px-3 py-1.5 text-sm" disabled={act.isPending}
                      onClick={() => act.mutate({ id: submitted.id, action: 'reopen' })}>Reopen for the customer</button>
                  )}
                </div>
                {showData && submitted.data && (
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-xl border border-white/5 bg-white/5 p-3 text-sm sm:grid-cols-2">
                    {FIELDS.filter(([k]) => show(submitted.data?.[k]) !== '').map(([k, label]) => (
                      <div key={k} className="min-w-0">
                        <dt className="text-xs text-grape-soft">{label}</dt>
                        <dd className="whitespace-pre-wrap break-words text-white">{show(submitted.data?.[k])}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            )}

            {pending && (
              <div className="flex flex-col gap-2" data-testid="intake-pending">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={pending.expired ? 'flamingo' : 'warning'}>{pending.expired ? 'Link expired' : 'Waiting for the customer'}</Badge>
                  <span className="text-xs text-grape-soft">
                    {pending.expired ? 'Expired' : 'Expires'} {when(pending.expires_at)}
                  </span>
                </div>
                {pending.token ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <input readOnly className="input min-w-[260px] flex-1 text-xs" value={linkFor(pending.token)}
                      onFocus={(e) => e.currentTarget.select()} aria-label="Customer link" data-testid="intake-link" />
                    <button type="button" className="btn-primary px-3 py-1.5 text-sm" onClick={() => copy(pending.token!)}>Copy link</button>
                  </div>
                ) : (
                  <p className="text-xs text-grape-soft">The link was only shown when it was created. Create a new one to copy it again.</p>
                )}
                {canWrite && (
                  <div className="flex gap-2">
                    <button type="button" className="btn-ghost px-3 py-1 text-xs" disabled={create.isPending} onClick={() => create.mutate()}>New link</button>
                    <button type="button" className="btn-ghost px-3 py-1 text-xs text-flamingo" disabled={act.isPending}
                      onClick={() => { if (confirm('Revoke this link? The customer will no longer be able to use it.')) act.mutate({ id: pending.id, action: 'revoke' }); }}>Revoke</button>
                  </div>
                )}
              </div>
            )}

            {!pending && !submitted && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-grape-soft">No link yet.</span>
                {canWrite && (
                  <button type="button" className="btn-primary px-3 py-1.5 text-sm" disabled={create.isPending}
                    data-testid="intake-create" onClick={() => create.mutate()}>Create link for the customer</button>
                )}
              </div>
            )}
            {submitted && !pending && canWrite && (
              <button type="button" className="self-start text-xs text-grape-soft underline" disabled={create.isPending}
                onClick={() => create.mutate()}>Create a new link</button>
            )}
          </>
        )}
      </div>
    </section>
  );
}
