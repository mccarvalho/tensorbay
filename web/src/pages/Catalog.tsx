// Product Catalog & Pricing — EPIC C / plan §8.
// Three tabs: SKUs, Price Books, Prices. Writes gated by pricing.write.
import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import {
  GPU_MODELS,
  COMMERCIAL_MODELS,
  SKU_CATEGORIES,
  PRICE_BOOK_SCOPES,
} from '../constants';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  type BadgeTone,
  type Column,
} from '../components/ui';

// --------------------------------------------------------------------------- //
interface Sku {
  id: string;
  code: string;
  name: string;
  category: string;
  gpu_model: string | null;
  description: string | null;
  active: boolean;
}
interface PriceBook {
  id: string;
  name: string;
  scope: string;
  currency: string | null;
  region: string | null;
  customer_id: string | null;
}
interface Price {
  id: string;
  sku_id: string;
  price_book_id: string;
  commercial_model: string;
  unit_price: string | number;
  unit: string;
  term_months: number | null;
}
interface CustomerLite {
  id: string;
  legal_name: string;
}

const CATEGORY_TONE: Record<string, BadgeTone> = {
  GPU: 'cyan', SERVER: 'grape', CLUSTER: 'flamingo', STORAGE: 'warning', NETWORK: 'neutral',
};
const SCOPE_TONE: Record<string, BadgeTone> = {
  LIST: 'neutral', REGIONAL: 'cyan', CUSTOMER: 'grape', CONTRACT: 'success',
  PROMO: 'warning', RESERVED: 'cyan', SPOT: 'flamingo',
};
const money = (v: string | number): string =>
  Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 });

type Tab = 'skus' | 'books' | 'prices';

// --------------------------------------------------------------------------- //
export default function Catalog() {
  const [tab, setTab] = useState<Tab>('skus');
  const canWrite = hasPermission('pricing.write');

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader
        eyebrow="COMMERCIAL · CATALOG"
        title="Product Catalog & Pricing"
        description="SKUs decouple hardware from offerings; price books hold list, customer, reserved and spot pricing; prices map a SKU in a book to a commercial model."
      />

      <div className="flex gap-1 border-b border-white/10">
        <TabButton active={tab === 'skus'} onClick={() => setTab('skus')}>SKUs</TabButton>
        <TabButton active={tab === 'books'} onClick={() => setTab('books')}>Price Books</TabButton>
        <TabButton active={tab === 'prices'} onClick={() => setTab('prices')}>Prices</TabButton>
      </div>

      {!canWrite && (
        <p className="text-xs text-grape-soft">
          You have read-only access to pricing. Contact a Sales Manager or admin to make changes.
        </p>
      )}

      {tab === 'skus' && <SkusTab canWrite={canWrite} />}
      {tab === 'books' && <PriceBooksTab canWrite={canWrite} />}
      {tab === 'prices' && <PricesTab canWrite={canWrite} />}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`-mb-px rounded-t-lg px-4 py-2 text-sm font-medium transition ${
        active ? 'border-b-2 border-cyan text-cyan' : 'text-grape-soft hover:text-white'
      }`}
    >
      {children}
    </button>
  );
}

// --------------------------------------------------------------------------- //
// SKUs
// --------------------------------------------------------------------------- //
function SkusTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ code: '', name: '', category: 'GPU', gpu_model: 'H200', description: '', active: true });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['skus'],
    queryFn: () => api.get<Sku[]>('/v1/catalog/skus?limit=500'),
  });

  function resetForm() {
    setEditId(null);
    setForm({ code: '', name: '', category: 'GPU', gpu_model: 'H200', description: '', active: true });
  }
  function openCreate() { resetForm(); setOpen(true); }
  function openEdit(s: Sku) {
    setEditId(s.id);
    setForm({
      code: s.code, name: s.name, category: s.category,
      gpu_model: s.gpu_model ?? 'H200', description: s.description ?? '', active: s.active,
    });
    setOpen(true);
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = {
        code: form.code,
        name: form.name,
        category: form.category,
        gpu_model: form.category === 'GPU' || form.category === 'SERVER' ? form.gpu_model || null : null,
        description: form.description || null,
        active: form.active,
      };
      return editId
        ? api.patch<Sku>(`/v1/catalog/skus/${editId}`, payload)
        : api.post<Sku>('/v1/catalog/skus', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['skus'] });
      setOpen(false);
      resetForm();
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/catalog/skus/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  });

  const columns: Array<Column<Sku>> = [
    { key: 'code', header: 'Code', render: (s) => <span className="font-semibold text-white">{s.code}</span> },
    { key: 'name', header: 'Name' },
    { key: 'category', header: 'Category', render: (s) => <Badge tone={CATEGORY_TONE[s.category] ?? 'neutral'}>{s.category}</Badge> },
    { key: 'gpu_model', header: 'GPU', render: (s) => s.gpu_model ?? '—' },
    { key: 'active', header: 'Active', render: (s) => <Badge tone={s.active ? 'success' : 'neutral'}>{s.active ? 'ACTIVE' : 'INACTIVE'}</Badge> },
    ...(canWrite
      ? [{
          key: 'actions', header: '', className: 'text-right',
          render: (s: Sku) => (
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(s)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete SKU ${s.code}?`)) deleteMut.mutate(s.id); }}>Delete</button>
            </div>
          ),
        } as Column<Sku>]
      : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      {canWrite && (
        <div className="flex justify-end">
          <button type="button" className="btn-primary" onClick={openCreate}>+ New SKU</button>
        </div>
      )}
      {deleteMut.isError && <ErrorState error={deleteMut.error} />}
      {isLoading ? <Spinner label="Loading SKUs…" /> : isError ? <ErrorState error={error} /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(s) => s.id}
          empty={<EmptyState title="No SKUs yet" hint="Create SKUs like GPU-H200-SXM or SERVER-8X-H200 to sell against." />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title={editId ? 'Edit SKU' : 'New SKU'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); saveMut.mutate(); }}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="s_code">Code</label>
              <input id="s_code" className="input" required placeholder="GPU-H200-SXM" value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="s_cat">Category</label>
              <select id="s_cat" className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {SKU_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label" htmlFor="s_name">Name</label>
            <input id="s_name" className="input" required placeholder="NVIDIA H200 SXM GPU" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          {(form.category === 'GPU' || form.category === 'SERVER') && (
            <div>
              <label className="label" htmlFor="s_gpu">GPU Model</label>
              <input id="s_gpu" className="input" list="sku-gpu-options" value={form.gpu_model}
                onChange={(e) => setForm({ ...form, gpu_model: e.target.value })} />
              <datalist id="sku-gpu-options">
                {GPU_MODELS.map((m) => <option key={m} value={m} />)}
              </datalist>
            </div>
          )}
          <div>
            <label className="label" htmlFor="s_desc">Description</label>
            <input id="s_desc" className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-grape-soft">
            <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
            Active
          </label>
          {saveMut.isError && <ErrorState error={saveMut.error} />}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); resetForm(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saveMut.isPending}>
              {saveMut.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create SKU'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Price Books
// --------------------------------------------------------------------------- //
function PriceBooksTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', scope: 'LIST', currency: 'USD', region: '', customer_id: '' });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['price-books'],
    queryFn: () => api.get<PriceBook[]>('/v1/catalog/price-books?limit=500'),
  });
  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
    enabled: open && form.scope === 'CUSTOMER',
  });

  function resetForm() {
    setEditId(null);
    setForm({ name: '', scope: 'LIST', currency: 'USD', region: '', customer_id: '' });
  }
  function openCreate() { resetForm(); setOpen(true); }
  function openEdit(b: PriceBook) {
    setEditId(b.id);
    setForm({
      name: b.name, scope: b.scope, currency: b.currency ?? 'USD',
      region: b.region ?? '', customer_id: b.customer_id ?? '',
    });
    setOpen(true);
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name,
        scope: form.scope,
        currency: form.currency || null,
        region: form.scope === 'REGIONAL' ? form.region || null : null,
        customer_id: form.scope === 'CUSTOMER' ? form.customer_id || null : null,
      };
      return editId
        ? api.patch<PriceBook>(`/v1/catalog/price-books/${editId}`, payload)
        : api.post<PriceBook>('/v1/catalog/price-books', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['price-books'] });
      setOpen(false);
      resetForm();
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/catalog/price-books/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['price-books'] }),
  });

  const columns: Array<Column<PriceBook>> = [
    { key: 'name', header: 'Name', render: (b) => <span className="font-semibold text-white">{b.name}</span> },
    { key: 'scope', header: 'Scope', render: (b) => <Badge tone={SCOPE_TONE[b.scope] ?? 'neutral'}>{b.scope}</Badge> },
    { key: 'currency', header: 'Currency', render: (b) => b.currency ?? '—' },
    { key: 'region', header: 'Region', render: (b) => b.region ?? '—' },
    ...(canWrite
      ? [{
          key: 'actions', header: '', className: 'text-right',
          render: (b: PriceBook) => (
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(b)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete price book "${b.name}"?`)) deleteMut.mutate(b.id); }}>Delete</button>
            </div>
          ),
        } as Column<PriceBook>]
      : []),
  ];

  return (
    <div className="flex flex-col gap-4">
      {canWrite && (
        <div className="flex justify-end">
          <button type="button" className="btn-primary" onClick={openCreate}>+ New Price Book</button>
        </div>
      )}
      {deleteMut.isError && <ErrorState error={deleteMut.error} />}
      {isLoading ? <Spinner label="Loading price books…" /> : isError ? <ErrorState error={error} /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(b) => b.id}
          empty={<EmptyState title="No price books yet" hint="Create a List price book, plus customer/reserved/spot books as needed." />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title={editId ? 'Edit Price Book' : 'New Price Book'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); saveMut.mutate(); }}>
          <div>
            <label className="label" htmlFor="b_name">Name</label>
            <input id="b_name" className="input" required placeholder="2026 List Price" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="b_scope">Scope</label>
              <select id="b_scope" className="input" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>
                {PRICE_BOOK_SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="b_cur">Currency</label>
              <input id="b_cur" className="input" maxLength={3} value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} />
            </div>
          </div>
          {form.scope === 'REGIONAL' && (
            <div>
              <label className="label" htmlFor="b_region">Region</label>
              <input id="b_region" className="input" placeholder="us-east-2" value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })} />
            </div>
          )}
          {form.scope === 'CUSTOMER' && (
            <div>
              <label className="label" htmlFor="b_customer">Customer</label>
              <select id="b_customer" className="input" value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                <option value="" disabled>{customersQuery.isLoading ? 'Loading…' : 'Select a customer'}</option>
                {customersQuery.data?.map((c) => <option key={c.id} value={c.id}>{c.legal_name}</option>)}
              </select>
            </div>
          )}
          {saveMut.isError && <ErrorState error={saveMut.error} />}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); resetForm(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saveMut.isPending}>
              {saveMut.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Price Book'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Prices
// --------------------------------------------------------------------------- //
function PricesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({
    sku_id: '', price_book_id: '', commercial_model: 'GPU_HOURLY', unit_price: 0, unit: 'GPU-hour', term_months: '',
  });

  const pricesQuery = useQuery({
    queryKey: ['prices'],
    queryFn: () => api.get<Price[]>('/v1/catalog/prices?limit=500'),
  });
  const skusQuery = useQuery({
    queryKey: ['skus'],
    queryFn: () => api.get<Sku[]>('/v1/catalog/skus?limit=500'),
  });
  const booksQuery = useQuery({
    queryKey: ['price-books'],
    queryFn: () => api.get<PriceBook[]>('/v1/catalog/price-books?limit=500'),
  });

  const skuName = useMemo(() => {
    const m = new Map((skusQuery.data ?? []).map((s) => [s.id, s.code]));
    return (id: string) => m.get(id) ?? id;
  }, [skusQuery.data]);
  const bookName = useMemo(() => {
    const m = new Map((booksQuery.data ?? []).map((b) => [b.id, b.name]));
    return (id: string) => m.get(id) ?? id;
  }, [booksQuery.data]);

  function resetForm() {
    setEditId(null);
    setForm({ sku_id: '', price_book_id: '', commercial_model: 'GPU_HOURLY', unit_price: 0, unit: 'GPU-hour', term_months: '' });
  }
  function openCreate() { resetForm(); setOpen(true); }
  function openEdit(p: Price) {
    setEditId(p.id);
    setForm({
      sku_id: p.sku_id, price_book_id: p.price_book_id, commercial_model: p.commercial_model,
      unit_price: Number(p.unit_price), unit: p.unit, term_months: p.term_months ? String(p.term_months) : '',
    });
    setOpen(true);
  }

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = {
        sku_id: form.sku_id,
        price_book_id: form.price_book_id,
        commercial_model: form.commercial_model,
        unit_price: Number(form.unit_price),
        unit: form.unit,
        term_months: form.term_months ? Number(form.term_months) : null,
      };
      return editId
        ? api.patch<Price>(`/v1/catalog/prices/${editId}`, payload)
        : api.post<Price>('/v1/catalog/prices', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prices'] });
      setOpen(false);
      resetForm();
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.del<void>(`/v1/catalog/prices/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prices'] }),
  });

  const columns: Array<Column<Price>> = [
    { key: 'sku_id', header: 'SKU', render: (p) => <span className="font-semibold text-white">{skuName(p.sku_id)}</span> },
    { key: 'price_book_id', header: 'Price Book', render: (p) => bookName(p.price_book_id) },
    { key: 'commercial_model', header: 'Model', render: (p) => <span className="text-xs text-grape-soft">{p.commercial_model}</span> },
    { key: 'unit_price', header: 'Unit Price', render: (p) => <span className="font-semibold text-cyan">{money(p.unit_price)}</span> },
    { key: 'unit', header: 'Unit' },
    { key: 'term_months', header: 'Term', render: (p) => (p.term_months ? `${p.term_months} mo` : '—') },
    ...(canWrite
      ? [{
          key: 'actions', header: '', className: 'text-right',
          render: (p: Price) => (
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={() => openEdit(p)}>Edit</button>
              <button type="button" className="btn-ghost px-2.5 py-1 text-xs text-flamingo"
                onClick={() => { if (confirm(`Delete price for ${skuName(p.sku_id)}?`)) deleteMut.mutate(p.id); }}>Delete</button>
            </div>
          ),
        } as Column<Price>]
      : []),
  ];

  const busy = pricesQuery.isLoading || skusQuery.isLoading || booksQuery.isLoading;

  return (
    <div className="flex flex-col gap-4">
      {canWrite && (
        <div className="flex justify-end">
          <button type="button" className="btn-primary" onClick={openCreate}>+ New Price</button>
        </div>
      )}
      {deleteMut.isError && <ErrorState error={deleteMut.error} />}
      {busy ? <Spinner label="Loading prices…" /> : pricesQuery.isError ? <ErrorState error={pricesQuery.error} /> : (
        <DataTable columns={columns} rows={pricesQuery.data ?? []} rowKey={(p) => p.id}
          empty={<EmptyState title="No prices yet" hint="Map a SKU in a price book to a commercial model and unit price." />} />
      )}

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title={editId ? 'Edit Price' : 'New Price'}>
        <form className="flex flex-col gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); saveMut.mutate(); }}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="p_sku">SKU</label>
              <select id="p_sku" className="input" required value={form.sku_id} onChange={(e) => setForm({ ...form, sku_id: e.target.value })}>
                <option value="" disabled>{skusQuery.isLoading ? 'Loading…' : 'Select SKU'}</option>
                {skusQuery.data?.map((s) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p_book">Price Book</label>
              <select id="p_book" className="input" required value={form.price_book_id} onChange={(e) => setForm({ ...form, price_book_id: e.target.value })}>
                <option value="" disabled>{booksQuery.isLoading ? 'Loading…' : 'Select price book'}</option>
                {booksQuery.data?.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.scope})</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="p_cm">Commercial Model</label>
              <select id="p_cm" className="input" value={form.commercial_model} onChange={(e) => setForm({ ...form, commercial_model: e.target.value })}>
                {COMMERCIAL_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="p_unit">Unit</label>
              <input id="p_unit" className="input" required placeholder="GPU-hour" value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="p_price">Unit Price (USD)</label>
              <input id="p_price" type="number" min={0} step="0.0001" className="input" required value={form.unit_price}
                onChange={(e) => setForm({ ...form, unit_price: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label" htmlFor="p_term">Term (months, optional)</label>
              <input id="p_term" type="number" min={1} className="input" value={form.term_months}
                onChange={(e) => setForm({ ...form, term_months: e.target.value })} />
            </div>
          </div>
          {saveMut.isError && <ErrorState error={saveMut.error} />}
          <div className="mt-2 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); resetForm(); }}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saveMut.isPending}>
              {saveMut.isPending ? 'Saving…' : editId ? 'Save Changes' : 'Create Price'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
