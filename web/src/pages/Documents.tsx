// AI Documents — showcases the Bedrock-backed document generation.
// Generate MSA / LOI / PROPOSAL / CONTRACT drafts, review the output, then
// approve or reject them.
import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { config } from '../config';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  type BadgeTone,
  type Column,
} from '../components/ui';

type DocType = 'MSA' | 'LOI' | 'PROPOSAL' | 'CONTRACT';
type DocStatus = 'DRAFT' | 'GENERATED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';

interface DocumentRecord {
  id: string;
  doc_type: DocType;
  title: string;
  status: DocStatus;
  customer_id: string | null;
  contract_id: string | null;
  model_id: string;
  prompt_summary: string | null;
  created_at: string;
}

interface GeneratedDocument extends DocumentRecord {
  content: string;
}

interface CustomerLite {
  id: string;
  legal_name: string;
}

interface GenerateRequest {
  doc_type: DocType;
  title: string;
  customer_id: string | null;
}

const DOC_TYPES: DocType[] = ['MSA', 'LOI', 'PROPOSAL', 'CONTRACT'];

const STATUS_TONE: Record<DocStatus, BadgeTone> = {
  DRAFT: 'neutral',
  GENERATED: 'cyan',
  UNDER_REVIEW: 'warning',
  APPROVED: 'success',
  REJECTED: 'flamingo',
};

export default function Documents() {
  const qc = useQueryClient();
  const [docType, setDocType] = useState<DocType>('PROPOSAL');
  const [title, setTitle] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [generated, setGenerated] = useState<GeneratedDocument | null>(null);

  const listQuery = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.get<DocumentRecord[]>('/v1/documents?limit=200'),
  });

  const customersQuery = useQuery({
    queryKey: ['customers', 'lite'],
    queryFn: () => api.get<CustomerLite[]>('/v1/customers?limit=200'),
  });

  const generateMut = useMutation({
    mutationFn: (payload: GenerateRequest) =>
      api.post<GeneratedDocument>('/v1/documents/generate', payload),
    onSuccess: (doc) => {
      setGenerated(doc);
      qc.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const approveMut = useMutation({
    mutationFn: (id: string) => api.post<DocumentRecord>(`/v1/documents/${id}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  });

  const rejectMut = useMutation({
    mutationFn: (id: string) => api.post<DocumentRecord>(`/v1/documents/${id}/reject`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  });

  const customerName = (id: string | null): string => {
    if (!id) return '—';
    return customersQuery.data?.find((c) => c.id === id)?.legal_name ?? id;
  };

  function submit(e: FormEvent) {
    e.preventDefault();
    setGenerated(null);
    generateMut.mutate({
      doc_type: docType,
      title: title.trim(),
      customer_id: customerId || null,
    });
  }

  const columns: Array<Column<DocumentRecord>> = [
    { key: 'title', header: 'Title', render: (d) => <span className="font-medium text-white">{d.title}</span> },
    { key: 'doc_type', header: 'Type', render: (d) => <Badge tone="grape">{d.doc_type}</Badge> },
    { key: 'customer_id', header: 'Customer', render: (d) => customerName(d.customer_id) },
    { key: 'model_id', header: 'Model', render: (d) => <span className="text-xs text-grape-soft">{d.model_id}</span> },
    { key: 'status', header: 'Status', render: (d) => <Badge tone={STATUS_TONE[d.status]}>{d.status}</Badge> },
    {
      key: 'actions',
      header: 'Review',
      render: (d) => {
        const pending =
          (approveMut.isPending && approveMut.variables === d.id) ||
          (rejectMut.isPending && rejectMut.variables === d.id);
        const decided = d.status === 'APPROVED' || d.status === 'REJECTED';
        if (decided) return <span className="text-xs text-grape-soft">Decided</span>;
        return (
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg bg-emerald-400/15 px-3 py-1 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-400/25 disabled:opacity-50"
              onClick={() => approveMut.mutate(d.id)}
              disabled={pending}
            >
              Approve
            </button>
            <button
              type="button"
              className="rounded-lg bg-flamingo/15 px-3 py-1 text-xs font-semibold text-flamingo transition hover:bg-flamingo/25 disabled:opacity-50"
              onClick={() => rejectMut.mutate(d.id)}
              disabled={pending}
            >
              Reject
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-10">
      <SectionHeader
        eyebrow="AI · AMAZON BEDROCK"
        title="AI Documents"
        description="Generate MSAs, LOIs, proposals, and contracts with Claude on Amazon Bedrock, then route them through approval."
      />

      {/* Generation panel — gated behind the aiDocs feature flag while the
          Anthropic model-access form is pending in the Bedrock console. */}
      {config.features.aiDocs ? (
        <section className="flex flex-col gap-4">
          <span className="eyebrow">GENERATE · DRAFT</span>
          <form className="card-glow flex flex-col gap-4" onSubmit={submit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="doc_type">Document Type</label>
              <select
                id="doc_type"
                className="input"
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocType)}
              >
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="doc_title">Title</label>
              <input
                id="doc_title"
                className="input"
                required
                placeholder="Acme Corp — Master Services Agreement"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="doc_customer">Customer (optional)</label>
              <select
                id="doc_customer"
                className="input"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
              >
                <option value="">
                  {customersQuery.isLoading ? 'Loading…' : 'No customer'}
                </option>
                {customersQuery.data?.map((c) => (
                  <option key={c.id} value={c.id}>{c.legal_name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end">
            <button type="submit" className="btn-primary" disabled={generateMut.isPending || title.trim().length === 0}>
              {generateMut.isPending ? 'Generating…' : 'Generate with Bedrock'}
            </button>
          </div>
        </form>

        {generateMut.isPending && <Spinner label="Claude is drafting your document…" />}
        {generateMut.isError && <ErrorState error={generateMut.error} />}
        {generated && (
          <div className="card flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <Badge tone="grape">{generated.doc_type}</Badge>
                <span className="font-medium text-white">{generated.title}</span>
              </div>
              <Badge tone={STATUS_TONE[generated.status]}>{generated.status}</Badge>
            </div>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-white/5 bg-space-900/60 p-4 text-sm text-grape-soft">
              {generated.content}
            </pre>
          </div>
        )}
      </section>
      ) : (
        <section className="flex flex-col gap-4">
          <span className="eyebrow">GENERATE · DRAFT</span>
          <div className="card flex flex-col items-center gap-3 py-10 text-center">
            <div className="h-10 w-10 rounded-xl bg-brand-gradient opacity-70" aria-hidden="true" />
            <h3 className="text-lg text-white">AI generation is being enabled</h3>
            <p className="max-w-lg text-sm text-grape-soft">
              Document generation with Amazon Bedrock (Claude) is wired up but
              temporarily disabled while model access is finalized in AWS. The
              document library below is fully functional in the meantime.
            </p>
            <Badge tone="warning">Coming soon</Badge>
          </div>
        </section>
      )}

      {/* Document library */}
      <section className="flex flex-col gap-4">
        <span className="eyebrow">LIBRARY · ALL DOCUMENTS</span>
        {(approveMut.isError || rejectMut.isError) && (
          <ErrorState error={approveMut.error ?? rejectMut.error} />
        )}
        {listQuery.isLoading ? (
          <Spinner label="Loading documents…" />
        ) : listQuery.isError ? (
          <ErrorState error={listQuery.error} />
        ) : (
          <DataTable
            columns={columns}
            rows={listQuery.data ?? []}
            rowKey={(d) => d.id}
            empty={<EmptyState title="No documents yet" hint="Generate your first AI document above." />}
          />
        )}
      </section>
    </div>
  );
}
