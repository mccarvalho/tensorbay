// Deal documents on the opportunity page: generate MSA / Order Form / NDA / Proposal /
// PoC / Escrow / Acceptance drafts as DOCX, download them, and see where they were
// filed in Google Drive. Every generation is a new version; a person reviews and approves.
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { config } from '../config';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from './toast';
import { Badge, EmptyState, ErrorState, Spinner, type BadgeTone } from './ui';

type DealDocType =
  | 'MSA' | 'ORDER_FORM' | 'NDA' | 'PROPOSAL' | 'POC_AGREEMENT' | 'ESCROW_AGREEMENT' | 'ACCEPTANCE_NOTICE';

interface DealDocument {
  id: string;
  doc_type: string;
  title: string;
  status: 'GENERATING' | 'FAILED' | 'DRAFT' | 'GENERATED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';
  version: number;
  file_name: string | null;
  error: string | null;
  drive_url: string | null;
  drive_error: string | null;
  created_at: string;
  created_by: string | null;
}

const TYPES: Array<{ type: DealDocType; label: string; how: string }> = [
  { type: 'PROPOSAL', label: 'Proposal', how: 'AI draft from the deal, quote and reference proposals' },
  { type: 'MSA', label: 'MSA + Order Form (Schedule A)', how: "Fills TensorBay's standard MSA; the legal text is not rewritten" },
  { type: 'ORDER_FORM', label: 'Order Form (standalone)', how: 'AI draft following Schedule A of the MSA' },
  { type: 'NDA', label: 'NDA', how: "Fills TensorBay's standard multilateral NDA" },
  { type: 'POC_AGREEMENT', label: 'PoC Agreement', how: 'AI draft for a paid PoC under the MSA' },
  { type: 'ESCROW_AGREEMENT', label: 'Escrow Agreement', how: 'AI draft from Schedule D, Part 2 of the MSA' },
  { type: 'ACCEPTANCE_NOTICE', label: 'Acceptance Notice', how: 'AI draft: Readiness Notice and Acceptance Certificate' },
];
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.type, t.label]));

const STATUS_TONE: Record<DealDocument['status'], BadgeTone> = {
  GENERATING: 'cyan', FAILED: 'flamingo', DRAFT: 'neutral', GENERATED: 'warning',
  UNDER_REVIEW: 'warning', APPROVED: 'success', REJECTED: 'flamingo',
};
const STATUS_LABEL: Record<DealDocument['status'], string> = {
  GENERATING: 'Generating…', FAILED: 'Failed', DRAFT: 'Draft', GENERATED: 'Draft · needs review',
  UNDER_REVIEW: 'Under review', APPROVED: 'Approved', REJECTED: 'Rejected',
};

export default function DealDocuments({ opportunityId }: { opportunityId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const canGenerate = hasPermission('document.generate');
  const canApprove = hasPermission('contract.write');
  const [docType, setDocType] = useState<DealDocType>('PROPOSAL');
  const [notes, setNotes] = useState('');
  const key = ['deal-documents', opportunityId];

  const docs = useQuery({
    queryKey: key,
    queryFn: () => api.get<DealDocument[]>(`/v1/documents/opportunity/${opportunityId}`),
    // Poll while a job is running.
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => d.status === 'GENERATING') ? 3000 : false),
  });

  const generate = useMutation({
    mutationFn: () => api.post<DealDocument>('/v1/documents/generate-for-opportunity', {
      opportunity_id: opportunityId, doc_type: docType, notes: notes.trim() || null,
    }),
    onSuccess: () => { toast.success('Generating. This takes up to a minute.'); qc.invalidateQueries({ queryKey: key }); },
    onError: (e) => toast.error(errMessage(e, 'Could not start the generation')),
  });

  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' | 'save-to-drive' }) =>
      api.post<DealDocument>(`/v1/documents/${id}/${action}`),
    onSuccess: (d, { action }) => {
      qc.invalidateQueries({ queryKey: key });
      if (action === 'save-to-drive') {
        if (d.drive_error) toast.error(d.drive_error); else toast.success('Saved to Google Drive');
      }
    },
    onError: (e) => toast.error(errMessage(e, 'Action failed')),
  });

  async function download(d: DealDocument) {
    try {
      const { blob, filename } = await api.download(`/v1/documents/${d.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(errMessage(e, 'Download failed'));
    }
  }

  const how = TYPES.find((t) => t.type === docType)?.how;

  return (
    <section id="documents" className="flex flex-col gap-4" data-testid="deal-documents">
      <span className="eyebrow">DOCUMENTS</span>

      {canGenerate && config.features.aiDocs && (
        <div className="card flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="deal_doc_type">Document</label>
              <select id="deal_doc_type" className="input" value={docType} onChange={(e) => setDocType(e.target.value as DealDocType)}>
                {TYPES.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
              </select>
              <p className="mt-1 text-xs text-grape-soft">{how}</p>
            </div>
            <div className="sm:col-span-2">
              <label className="label" htmlFor="deal_doc_notes">Notes for this draft (optional)</label>
              <textarea
                id="deal_doc_notes" className="input" rows={2} maxLength={4000}
                placeholder="e.g. escrow agent, special payment terms, anything the CRM does not know"
                value={notes} onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-grape-soft">
              Built from this deal, its customer, contacts and quote. The DOCX is saved to Google Drive under
              Clients / customer / deal / document type. Always a draft: review before sending.
            </p>
            <button type="button" className="btn-primary whitespace-nowrap" disabled={generate.isPending} onClick={() => generate.mutate()}>
              {generate.isPending ? 'Starting…' : 'Generate document'}
            </button>
          </div>
        </div>
      )}

      {docs.isLoading ? (
        <Spinner label="Loading documents…" />
      ) : docs.isError ? (
        <ErrorState error={docs.error} />
      ) : (docs.data ?? []).length === 0 ? (
        <EmptyState title="No documents yet" hint="Generate a proposal, MSA or other document for this deal." />
      ) : (
        <div className="flex flex-col gap-2">
          {(docs.data ?? []).map((d) => (
            <div key={d.id} data-testid={`doc-${d.id}`} className="card flex flex-col gap-2 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-white">{TYPE_LABEL[d.doc_type] ?? d.doc_type}</span>
                  <span className="text-xs text-grape-soft">v{d.version}</span>
                  <Badge tone={STATUS_TONE[d.status]}>{STATUS_LABEL[d.status]}</Badge>
                  <span className="text-xs text-grape-soft">{new Date(d.created_at).toLocaleString()}</span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {d.status !== 'GENERATING' && d.status !== 'FAILED' && (
                    <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => download(d)}>Download DOCX</button>
                  )}
                  {d.drive_url && (
                    <a className="btn-ghost px-2 py-0.5 text-xs" href={d.drive_url} target="_blank" rel="noreferrer">Open in Drive</a>
                  )}
                  {canGenerate && d.drive_error && (
                    <button type="button" className="btn-ghost px-2 py-0.5 text-xs" disabled={act.isPending}
                      onClick={() => act.mutate({ id: d.id, action: 'save-to-drive' })}>Save to Drive</button>
                  )}
                  {canApprove && d.status === 'GENERATED' && (
                    <>
                      <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => act.mutate({ id: d.id, action: 'approve' })}>Approve</button>
                      <button type="button" className="btn-ghost px-2 py-0.5 text-xs" onClick={() => act.mutate({ id: d.id, action: 'reject' })}>Reject</button>
                    </>
                  )}
                </div>
              </div>
              {d.file_name && <div className="truncate text-xs text-grape-soft">{d.file_name}</div>}
              {d.status === 'FAILED' && d.error && <div className="text-xs text-flamingo">{d.error}</div>}
              {d.drive_error && d.status !== 'FAILED' && <div className="text-xs text-flamingo">Drive: {d.drive_error}</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
