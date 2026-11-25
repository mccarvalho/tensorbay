// Public page (no login): the customer fills in the data for their MSA and Order Form.
// The long random token in the link is the only credential. English only: customers
// are international.
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { config } from '../config';

interface FormInfo {
  status: 'PENDING' | 'SUBMITTED';
  customer_name: string;
  gpu_model: string;
  quantity: number;
  contact_name: string | null;
  expires_at: string;
  prefill: Record<string, unknown> | null;
}

interface Values {
  legal_name: string; company_form: string; jurisdiction: string; registration_number: string;
  registered_address: string; website: string;
  signatory_name: string; signatory_title: string; signatory_email: string;
  notices_email: string;
  technical_contact_name: string; technical_contact_email: string; technical_contact_phone: string;
  billing_contact_name: string; billing_contact_email: string; billing_contact_phone: string;
  workload_description: string; compute_fabric: string;
  shared_storage_tb: string; dedicated_internet_gbps: string; monthly_egress_tb: string;
  access_methods: string[]; allowed_ip_addresses: string; os_image_notes: string;
  region_preference: string; preferred_start_date: string; additional_notes: string;
  confirm_accuracy: boolean;
}

const EMPTY: Values = {
  legal_name: '', company_form: '', jurisdiction: '', registration_number: '', registered_address: '', website: '',
  signatory_name: '', signatory_title: '', signatory_email: '', notices_email: '',
  technical_contact_name: '', technical_contact_email: '', technical_contact_phone: '',
  billing_contact_name: '', billing_contact_email: '', billing_contact_phone: '',
  workload_description: '', compute_fabric: 'NO_PREFERENCE', shared_storage_tb: '', dedicated_internet_gbps: '',
  monthly_egress_tb: '', access_methods: [], allowed_ip_addresses: '', os_image_notes: '', region_preference: '',
  preferred_start_date: '', additional_notes: '', confirm_accuracy: false,
};

const LABELS: Record<string, string> = {
  legal_name: 'Legal name', company_form: 'Company form', jurisdiction: 'Jurisdiction',
  registration_number: 'Registration number', registered_address: 'Registered address',
  signatory_name: 'Signatory name', signatory_title: 'Signatory title', signatory_email: 'Signatory email',
  notices_email: 'Email for notices', technical_contact_email: 'Technical contact email',
  billing_contact_email: 'Billing contact email', confirm_accuracy: 'Confirmation',
  shared_storage_tb: 'Shared storage', dedicated_internet_gbps: 'Internet bandwidth', monthly_egress_tb: 'Monthly egress',
};

const api = (path: string) => `${config.apiBaseUrl}/v1/public/intake/${path}`;

async function readError(resp: Response): Promise<{ message: string; fields: Record<string, string> }> {
  const fields: Record<string, string> = {};
  try {
    const body = await resp.json();
    if (Array.isArray(body.detail)) {
      for (const d of body.detail as Array<{ loc: string[]; msg: string }>) {
        const key = d.loc[d.loc.length - 1];
        fields[key] = d.msg.replace(/^Value error, /, '');
      }
      return { message: 'Please check the highlighted fields.', fields };
    }
    if (typeof body.detail === 'string') return { message: body.detail, fields };
  } catch { /* not JSON */ }
  return { message: 'Something went wrong. Please try again.', fields };
}

// Defined at module level so inputs keep focus while typing (a component created inside
// the page would be a new type on every render and remount its children).
function FieldBox({ id, label, required, hint, error, children }: {
  id: string; label: string; required?: boolean; hint?: string; error?: string; children: ReactNode;
}) {
  return (
    <div>
      <label className="label" htmlFor={`f_${id}`}>{label}{required && <span className="text-flamingo"> *</span>}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-grape-soft">{hint}</p>}
      {error && <p className="mt-1 text-xs text-flamingo" role="alert">{LABELS[id] ?? label}: {error}</p>}
    </div>
  );
}

export default function CustomerIntake() {
  const { token = '' } = useParams();
  const [info, setInfo] = useState<FormInfo | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [v, setV] = useState<Values>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    document.title = 'TensorBay · Order Form details';
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex,nofollow';
    document.head.appendChild(meta);
    return () => { document.head.removeChild(meta); };
  }, []);

  useEffect(() => {
    fetch(api(token), { cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) { setFatal((await readError(r)).message); return; }
        const data: FormInfo = await r.json();
        setInfo(data);
        if (data.status === 'SUBMITTED') { setDone(true); return; }
        const pre = (data.prefill ?? {}) as Record<string, unknown>;
        const next = { ...EMPTY };
        for (const k of Object.keys(EMPTY) as Array<keyof Values>) {
          const val = pre[k];
          if (val === null || val === undefined) continue;
          if (k === 'access_methods') next.access_methods = val as string[];
          else if (k === 'confirm_accuracy') next.confirm_accuracy = false; // always confirmed again
          else (next as Record<string, unknown>)[k] = String(val);
        }
        setV(next);
      })
      .catch(() => setFatal('We could not load this page. Please check your connection and try again.'));
  }, [token]);

  const set = (k: keyof Values, value: string | boolean | string[]) => setV((cur) => ({ ...cur, [k]: value }));
  const num = (s: string) => (s.trim() === '' ? null : Number(s));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setFieldErrors({});
    const body = {
      ...v,
      shared_storage_tb: num(v.shared_storage_tb),
      dedicated_internet_gbps: num(v.dedicated_internet_gbps),
      monthly_egress_tb: num(v.monthly_egress_tb),
      preferred_start_date: v.preferred_start_date || null,
      technical_contact_email: v.technical_contact_email || null,
      billing_contact_email: v.billing_contact_email || null,
    };
    try {
      const r = await fetch(api(token), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (r.ok) { setDone(true); window.scrollTo({ top: 0 }); return; }
      const err = await readError(r);
      setError(err.message); setFieldErrors(err.fields);
      if (Object.keys(err.fields).length) window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      setError('We could not send the form. Please check your connection and try again.');
    } finally {
      setBusy(false);
    }
  }

  const text = (id: keyof Values, label: string, opts: { required?: boolean; hint?: string; type?: string; placeholder?: string } = {}) => (
    <FieldBox id={id} label={label} required={opts.required} hint={opts.hint} error={fieldErrors[id]}>
      <input id={`f_${id}`} className="input" type={opts.type ?? 'text'} required={opts.required} maxLength={255}
        placeholder={opts.placeholder} value={v[id] as string} onChange={(e) => set(id, e.target.value)} />
    </FieldBox>
  );
  const area = (id: keyof Values, label: string, opts: { required?: boolean; hint?: string; rows?: number; placeholder?: string } = {}) => (
    <FieldBox id={id} label={label} required={opts.required} hint={opts.hint} error={fieldErrors[id]}>
      <textarea id={`f_${id}`} className="input" rows={opts.rows ?? 3} required={opts.required} maxLength={2000}
        placeholder={opts.placeholder} value={v[id] as string} onChange={(e) => set(id, e.target.value)} />
    </FieldBox>
  );
  const number = (id: keyof Values, label: string, unit: string) => (
    <FieldBox id={id} label={label} hint={unit} error={fieldErrors[id]}>
      <input id={`f_${id}`} className="input" type="number" min={0} value={v[id] as string} onChange={(e) => set(id, e.target.value)} />
    </FieldBox>
  );

  const shell = (children: ReactNode) => (
    <div className="min-h-screen px-4 py-10">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div className="text-center">
          <div className="text-2xl font-extrabold text-white">TensorBay</div>
          <div className="mt-1 text-xs uppercase tracking-[0.25em] text-grape-soft">GPU Cloud &amp; AI Infrastructure</div>
        </div>
        {children}
        <p className="text-center text-xs text-grape-soft">This page is private to you. Please do not share the link.</p>
      </div>
    </div>
  );

  if (fatal) {
    return shell(
      <div className="card-glow text-center">
        <h1 className="text-xl">This link cannot be used</h1>
        <p className="mt-2 text-sm text-grape-soft" data-testid="intake-fatal">{fatal}</p>
      </div>,
    );
  }
  if (!info) return shell(<p className="text-center text-sm text-grape-soft">Loading…</p>);
  if (done) {
    return shell(
      <div className="card-glow text-center" data-testid="intake-done">
        <h1 className="text-xl">Thank you</h1>
        <p className="mt-2 text-sm text-grape-soft">
          We received the details for {info.customer_name}.{info.contact_name ? ` ${info.contact_name} at TensorBay has been notified` : ' Your TensorBay contact has been notified'} and will prepare your Master Services Agreement and Order Form.
        </p>
        <p className="mt-2 text-xs text-grape-soft">If anything needs to change, please contact your TensorBay representative.</p>
      </div>,
    );
  }

  return shell(
    <form className="flex flex-col gap-6" onSubmit={submit} noValidate={false}>
      <div className="card-glow">
        <span className="eyebrow">ORDER FORM DETAILS</span>
        <h1 className="mt-1 text-xl">{info.customer_name}</h1>
        <p className="mt-2 text-sm text-grape-soft">
          To prepare your Master Services Agreement and Order Form for{' '}
          <b className="text-white">{info.quantity.toLocaleString('en-US')} × {info.gpu_model}</b>, please complete the details below.
          Fields marked <span className="text-flamingo">*</span> are required. The link expires on {new Date(info.expires_at).toLocaleDateString('en-US', { dateStyle: 'long' })}.
        </p>
        {error && <p className="mt-3 rounded-xl bg-flamingo/10 p-3 text-sm text-flamingo" role="alert" data-testid="intake-error">{error}</p>}
      </div>

      <section className="card flex flex-col gap-4">
        <span className="eyebrow">YOUR COMPANY</span>
        {text('legal_name', 'Legal name', { required: true })}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {text('company_form', 'Company form', { required: true, placeholder: 'e.g. limited liability company', hint: 'As in your registration documents' })}
          {text('jurisdiction', 'Where it is organized', { required: true, placeholder: 'e.g. Delaware, USA' })}
        </div>
        {text('registration_number', 'Registration number', { required: true, hint: 'Company registration or tax ID' })}
        {area('registered_address', 'Registered address', { required: true, rows: 2 })}
        {text('website', 'Website')}
      </section>

      <section className="card flex flex-col gap-4">
        <span className="eyebrow">WHO SIGNS</span>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {text('signatory_name', 'Full name', { required: true })}
          {text('signatory_title', 'Title', { required: true })}
        </div>
        {text('signatory_email', 'Email', { required: true, type: 'email' })}
        {text('notices_email', 'Email for contract notices', { required: true, type: 'email', hint: 'Where formal notices under the agreement are sent' })}
      </section>

      <section className="card flex flex-col gap-4">
        <span className="eyebrow">CONTACTS</span>
        <p className="-mt-2 text-xs text-grape-soft">Technical contact (access and operations)</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {text('technical_contact_name', 'Name')}
          {text('technical_contact_email', 'Email', { type: 'email' })}
          {text('technical_contact_phone', 'Phone')}
        </div>
        <p className="text-xs text-grape-soft">Billing contact (invoices)</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {text('billing_contact_name', 'Name')}
          {text('billing_contact_email', 'Email', { type: 'email' })}
          {text('billing_contact_phone', 'Phone')}
        </div>
      </section>

      <section className="card flex flex-col gap-4">
        <span className="eyebrow">YOUR ENVIRONMENT</span>
        {area('workload_description', 'What will you run?', { placeholder: 'e.g. pre-training a large language model; inference serving', rows: 3 })}
        <FieldBox id="compute_fabric" label="Compute fabric" error={fieldErrors.compute_fabric}>
          <select id="f_compute_fabric" className="input" value={v.compute_fabric} onChange={(e) => set('compute_fabric', e.target.value)}>
            <option value="NO_PREFERENCE">No preference</option>
            <option value="INFINIBAND">NVIDIA Quantum InfiniBand</option>
            <option value="ROCE">RoCE v2 Ethernet</option>
          </select>
        </FieldBox>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {number('shared_storage_tb', 'Shared storage', 'TB usable')}
          {number('dedicated_internet_gbps', 'Internet bandwidth', 'Gb/s')}
          {number('monthly_egress_tb', 'Monthly egress', 'TB per month')}
        </div>
        <fieldset>
          <legend className="label">How will you connect?</legend>
          <div className="flex flex-wrap gap-4 text-sm text-white">
            {[['SSH', 'SSH over the internet'], ['VPN', 'VPN'], ['DIRECT_CONNECT', 'Direct connect']].map(([k, label]) => (
              <label key={k} className="flex items-center gap-2">
                <input type="checkbox" checked={v.access_methods.includes(k)}
                  onChange={(e) => set('access_methods', e.target.checked ? [...v.access_methods, k] : v.access_methods.filter((x) => x !== k))} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        {area('allowed_ip_addresses', 'IP addresses or ranges that need access', { rows: 2, placeholder: 'e.g. 203.0.113.0/24' })}
        {area('os_image_notes', 'Operating system, drivers or software requirements', { rows: 2 })}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {text('region_preference', 'Preferred region or site')}
          <FieldBox id="preferred_start_date" label="Preferred start date" error={fieldErrors.preferred_start_date}>
            <input id="f_preferred_start_date" className="input" type="date" value={v.preferred_start_date} onChange={(e) => set('preferred_start_date', e.target.value)} />
          </FieldBox>
        </div>
        {area('additional_notes', 'Anything else we should know', { rows: 3 })}
      </section>

      <section className="card flex flex-col gap-4">
        <label className="flex items-start gap-2 text-sm text-white">
          <input id="f_confirm_accuracy" type="checkbox" className="mt-1" checked={v.confirm_accuracy} onChange={(e) => set('confirm_accuracy', e.target.checked)} required />
          I confirm the information above is accurate and that I am authorized to provide it on behalf of {info.customer_name}.
        </label>
        {fieldErrors.confirm_accuracy && <p className="text-xs text-flamingo" role="alert">{fieldErrors.confirm_accuracy}</p>}
        <button type="submit" className="btn-primary" disabled={busy} data-testid="intake-submit">{busy ? 'Sending…' : 'Submit'}</button>
      </section>
    </form>,
  );
}
