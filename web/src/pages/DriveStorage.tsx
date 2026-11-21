// Google Drive storage for generated documents (Super Admin).
// Connect the crm@ Google account, point the portal at the shared root folder
// (e.g. "CRM TensorBay"), and check it can write there. Documents are filed under
// Clientes/<customer>/<opportunity or contract>/<document type>/.
import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { hasPermission } from '../permissions';
import { useToast, errMessage } from '../components/toast';
import { Badge, Spinner, ErrorState } from '../components/ui';

interface DriveStatus {
  configured: boolean; connected: boolean; account_email: string | null; connected_by: string | null;
  connected_at: string | null; needs_reconnect: boolean; last_error: string | null;
  root_folder_id: string | null; root_folder_name: string | null; root_folder_url: string | null; redirect_uri: string;
}
interface Folder { id: string; name: string; url: string | null; can_write: boolean }

export default function DriveStorage() {
  const isAdmin = hasPermission('user.admin');
  const qc = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState('CRM TensorBay');
  const [link, setLink] = useState('');
  const [results, setResults] = useState<Folder[] | null>(null);
  const status = useQuery({ queryKey: ['drive', 'status'], queryFn: () => api.get<DriveStatus>('/v1/drive/status') });
  const refresh = () => qc.invalidateQueries({ queryKey: ['drive', 'status'] });

  const connect = useMutation({
    mutationFn: () => api.post<{ authorization_url: string }>('/v1/drive/connect', {}),
    onSuccess: (r) => { window.location.href = r.authorization_url; },
    onError: (e) => toast.error(errMessage(e, 'Could not start the Google sign-in')),
  });
  const find = useMutation({
    mutationFn: () => api.get<Folder[]>(`/v1/drive/folders?name=${encodeURIComponent(search.trim())}`),
    onSuccess: setResults,
    onError: (e) => toast.error(errMessage(e, 'Could not search Drive')),
  });
  const setRoot = useMutation({
    mutationFn: (folder: string) => api.put<DriveStatus>('/v1/drive/root', { folder }),
    onSuccess: (s) => { toast.success(`Documents will be saved in “${s.root_folder_name}”`); setResults(null); setLink(''); refresh(); },
    onError: (e) => toast.error(errMessage(e, 'Could not use that folder')),
  });
  const check = useMutation({
    mutationFn: () => api.post<{ ok: boolean; file_url: string | null; folder_path: string }>('/v1/drive/check', {}),
    onSuccess: (r) => toast.success(`Write check OK: created ${r.folder_path}/LEIA-ME (portal).txt`),
    onError: (e) => toast.error(errMessage(e, 'Write check failed')),
  });
  const disconnect = useMutation({
    mutationFn: () => api.post<DriveStatus>('/v1/drive/disconnect', {}),
    onSuccess: () => { toast.success('Google Drive disconnected'); refresh(); },
    onError: (e) => toast.error(errMessage(e, 'Could not disconnect')),
  });

  if (status.isLoading) return <Spinner label="Loading Google Drive…" />;
  if (status.isError) return <ErrorState error={status.error} />;
  const s = status.data!;

  return (
    <section className="card flex flex-col gap-4" data-testid="drive-storage">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="eyebrow">STORAGE · GOOGLE DRIVE</span>
          <span className="text-sm text-grape-soft">
            Documents are saved as DOCX in <span className="text-white">Clientes / cliente / oportunidade / tipo</span>.
          </span>
        </div>
        {s.needs_reconnect ? <Badge tone="flamingo">reconnect needed</Badge>
          : s.connected ? <Badge tone="success">connected</Badge> : <Badge tone="neutral">not connected</Badge>}
      </div>

      {!s.configured && <p className="text-sm text-flamingo">Google sign-in is not configured for this environment.</p>}

      <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-xs text-grape-soft">Google account</dt><dd className="text-white">{s.account_email ?? '—'}</dd></div>
        <div><dt className="text-xs text-grape-soft">Root folder</dt><dd className="text-white">
          {s.root_folder_name ? (s.root_folder_url ? <a className="text-cyan hover:underline" href={s.root_folder_url} target="_blank" rel="noreferrer">{s.root_folder_name}</a> : s.root_folder_name) : '—'}
        </dd></div>
        <div><dt className="text-xs text-grape-soft">Connected by</dt><dd className="text-white">{s.connected_by ?? '—'}</dd></div>
      </dl>
      {s.last_error && <p className="text-sm text-flamingo">{s.last_error}</p>}

      {isAdmin && (
        <>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary px-3 py-1.5 text-sm" disabled={!s.configured || connect.isPending}
              onClick={() => connect.mutate()}>{s.connected || s.needs_reconnect ? 'Reconnect Google Drive' : 'Connect Google Drive'}</button>
            {s.connected && s.root_folder_id && (
              <button type="button" className="btn-ghost px-3 py-1.5 text-sm" disabled={check.isPending} onClick={() => check.mutate()}>
                {check.isPending ? 'Checking…' : 'Test write'}</button>
            )}
            {s.connected && (
              <button type="button" className="btn-ghost px-3 py-1.5 text-sm"
                onClick={() => { if (confirm('Disconnect Google Drive? New documents will no longer be saved to Drive.')) disconnect.mutate(); }}>Disconnect</button>
            )}
          </div>

          {s.connected && !s.needs_reconnect && (
            <div className="flex flex-col gap-3 rounded-xl border border-white/10 p-3">
              <span className="label">{s.root_folder_id ? 'Change root folder' : 'Choose the root folder'}</span>
              <form className="flex flex-wrap gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); find.mutate(); }}>
                <input className="input min-w-[240px] flex-1" aria-label="Folder name" value={search} onChange={(e) => setSearch(e.target.value)} />
                <button type="submit" className="btn-ghost px-3 py-1.5 text-sm" disabled={find.isPending}>Find folder</button>
              </form>
              {results && (results.length === 0 ? <p className="text-sm text-grape-soft">No folder with that name is shared with {s.account_email}.</p> : (
                <ul className="flex flex-col gap-1.5">
                  {results.map((f) => (
                    <li key={f.id} className="flex items-center justify-between gap-2 text-sm">
                      <span className="text-white">{f.name} {!f.can_write && <span className="text-xs text-flamingo">(view only)</span>}</span>
                      <button type="button" className="btn-primary px-2.5 py-1 text-xs" disabled={!f.can_write || setRoot.isPending}
                        onClick={() => setRoot.mutate(f.id)}>Use this folder</button>
                    </li>
                  ))}
                </ul>
              ))}
              <form className="flex flex-wrap gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); setRoot.mutate(link.trim()); }}>
                <input className="input min-w-[240px] flex-1" aria-label="Folder link" placeholder="…or paste the folder link from Google Drive"
                  value={link} onChange={(e) => setLink(e.target.value)} />
                <button type="submit" className="btn-ghost px-3 py-1.5 text-sm" disabled={!link.trim() || setRoot.isPending}>Use link</button>
              </form>
            </div>
          )}
        </>
      )}
    </section>
  );
}
