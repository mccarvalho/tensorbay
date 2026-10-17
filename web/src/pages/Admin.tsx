// Admin — invite-based user management & role assignment (SUPER_ADMIN only).
import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import {
  SectionHeader,
  Spinner,
  ErrorState,
  EmptyState,
  DataTable,
  Badge,
  Modal,
  type Column,
} from '../components/ui';

interface AdminUser {
  username: string;
  email: string | null;
  name: string | null;
  status: string;
  enabled: boolean;
  created_at: string | null;
  roles: string[];
}

interface RolesCatalog {
  roles: string[];
}

function statusTone(status: string, enabled: boolean): 'success' | 'warning' | 'neutral' | 'flamingo' {
  if (!enabled) return 'flamingo';
  if (status === 'CONFIRMED') return 'success';
  if (status === 'FORCE_CHANGE_PASSWORD') return 'warning';
  return 'neutral';
}

export default function Admin() {
  const qc = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [rolesFor, setRolesFor] = useState<AdminUser | null>(null);

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api.get<AdminUser[]>('/v1/admin/users'),
  });

  const rolesQuery = useQuery({
    queryKey: ['admin', 'roles'],
    queryFn: () => api.get<RolesCatalog>('/v1/admin/roles'),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin', 'users'] });

  const inviteMut = useMutation({
    mutationFn: (payload: { email: string; name: string; roles: string[] }) =>
      api.post<AdminUser>('/v1/admin/users', payload),
    onSuccess: () => {
      invalidate();
      setInviteOpen(false);
    },
  });

  const rolesMut = useMutation({
    mutationFn: ({ username, roles }: { username: string; roles: string[] }) =>
      api.put<AdminUser>(`/v1/admin/users/${encodeURIComponent(username)}/roles`, { roles }),
    onSuccess: () => {
      invalidate();
      setRolesFor(null);
    },
  });

  const toggleMut = useMutation({
    mutationFn: ({ username, enable }: { username: string; enable: boolean }) =>
      api.post<AdminUser>(
        `/v1/admin/users/${encodeURIComponent(username)}/${enable ? 'enable' : 'disable'}`,
      ),
    onSuccess: invalidate,
  });

  const deleteMut = useMutation({
    mutationFn: (username: string) =>
      api.del<void>(`/v1/admin/users/${encodeURIComponent(username)}`),
    onSuccess: invalidate,
  });

  const columns: Array<Column<AdminUser>> = [
    {
      key: 'email',
      header: 'User',
      render: (u) => (
        <div className="flex flex-col">
          <span className="font-medium text-white">{u.email ?? u.username}</span>
          {u.name && <span className="text-xs text-grape-soft">{u.name}</span>}
        </div>
      ),
    },
    {
      key: 'roles',
      header: 'Roles',
      render: (u) =>
        u.roles.length ? (
          <div className="flex flex-wrap gap-1">
            {u.roles.map((r) => (
              <Badge key={r} tone={r === 'SUPER_ADMIN' ? 'cyan' : 'grape'}>
                {r}
              </Badge>
            ))}
          </div>
        ) : (
          <span className="text-xs text-grape-soft">No roles</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (u) => (
        <Badge tone={statusTone(u.status, u.enabled)}>
          {u.enabled ? u.status : 'DISABLED'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Manage',
      render: (u) => (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg bg-cyan/15 px-3 py-1 text-xs font-semibold text-cyan transition hover:bg-cyan/25"
            onClick={() => setRolesFor(u)}
          >
            Roles
          </button>
          <button
            type="button"
            className="rounded-lg bg-white/10 px-3 py-1 text-xs font-semibold text-grape-soft transition hover:bg-white/20"
            onClick={() => toggleMut.mutate({ username: u.username, enable: !u.enabled })}
            disabled={toggleMut.isPending}
          >
            {u.enabled ? 'Disable' : 'Enable'}
          </button>
          <button
            type="button"
            className="rounded-lg bg-flamingo/15 px-3 py-1 text-xs font-semibold text-flamingo transition hover:bg-flamingo/25"
            onClick={() => {
              if (confirm(`Delete ${u.email ?? u.username}? This cannot be undone.`)) {
                deleteMut.mutate(u.username);
              }
            }}
            disabled={deleteMut.isPending}
          >
            Delete
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeader
          eyebrow="ADMIN · ACCESS CONTROL"
          title="Users & Roles"
          description="Invite team members and assign roles. Invited users receive an email and sign in with Google Workspace SSO."
        />
        <button type="button" className="btn-primary" onClick={() => setInviteOpen(true)}>
          + Invite User
        </button>
      </div>

      {(toggleMut.isError || deleteMut.isError) && (
        <ErrorState error={toggleMut.error ?? deleteMut.error} />
      )}

      {usersQuery.isLoading ? (
        <Spinner label="Loading users…" />
      ) : usersQuery.isError ? (
        <ErrorState error={usersQuery.error} />
      ) : (
        <DataTable
          columns={columns}
          rows={usersQuery.data ?? []}
          rowKey={(u) => u.username}
          empty={<EmptyState title="No users yet" hint="Invite your first team member." />}
        />
      )}

      {inviteOpen && (
        <InviteModal
          roles={rolesQuery.data?.roles ?? []}
          pending={inviteMut.isPending}
          error={inviteMut.isError ? inviteMut.error : null}
          onClose={() => setInviteOpen(false)}
          onSubmit={(email, name, roles) => inviteMut.mutate({ email, name, roles })}
        />
      )}

      {rolesFor && (
        <RolesModal
          user={rolesFor}
          roles={rolesQuery.data?.roles ?? []}
          pending={rolesMut.isPending}
          error={rolesMut.isError ? rolesMut.error : null}
          onClose={() => setRolesFor(null)}
          onSubmit={(roles) => rolesMut.mutate({ username: rolesFor.username, roles })}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Invite modal
// --------------------------------------------------------------------------- //
function InviteModal(props: {
  roles: string[];
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (email: string, name: string, roles: string[]) => void;
}) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(role: string) {
    setSelected((s) => (s.includes(role) ? s.filter((r) => r !== role) : [...s, role]));
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    props.onSubmit(email.trim(), name.trim(), selected);
  }

  return (
    <Modal open onClose={props.onClose} title="Invite User">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div>
          <label className="label" htmlFor="invite_email">Work Email</label>
          <input
            id="invite_email"
            type="email"
            className="input"
            required
            placeholder="person@tensorbay.io"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="invite_name">Name (optional)</label>
          <input
            id="invite_name"
            className="input"
            placeholder="Jane Doe"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <span className="label">Roles</span>
          <RoleChips all={props.roles} selected={selected} onToggle={toggle} />
        </div>
        {props.error ? <ErrorState error={props.error} /> : null}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={props.onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={props.pending || !email}>
            {props.pending ? 'Inviting…' : 'Send Invite'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
// Roles modal
// --------------------------------------------------------------------------- //
function RolesModal(props: {
  user: AdminUser;
  roles: string[];
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (roles: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>(props.user.roles);

  function toggle(role: string) {
    setSelected((s) => (s.includes(role) ? s.filter((r) => r !== role) : [...s, role]));
  }

  return (
    <Modal open onClose={props.onClose} title={`Roles — ${props.user.email ?? props.user.username}`}>
      <div className="flex flex-col gap-4">
        <RoleChips all={props.roles} selected={selected} onToggle={toggle} />
        {props.error ? <ErrorState error={props.error} /> : null}
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" className="btn-ghost" onClick={props.onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={props.pending}
            onClick={() => props.onSubmit(selected)}
          >
            {props.pending ? 'Saving…' : 'Save Roles'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function RoleChips(props: {
  all: string[];
  selected: string[];
  onToggle: (role: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {props.all.map((role) => {
        const on = props.selected.includes(role);
        return (
          <button
            key={role}
            type="button"
            onClick={() => props.onToggle(role)}
            className={`badge cursor-pointer transition ${
              on ? 'bg-brand-gradient text-space-900' : 'bg-white/10 text-grape-soft hover:bg-white/20'
            }`}
          >
            {role}
          </button>
        );
      })}
    </div>
  );
}
