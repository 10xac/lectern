import { useState, type FormEvent } from 'react';
import { api, type User } from '../api';
import { Button } from '../components/ui/Button';
import { ConfirmButton } from '../components/ui/ConfirmButton';
import { CreatePanel } from '../components/ui/CreatePanel';
import { DataTable, type Column } from '../components/ui/DataTable';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input, Select } from '../components/ui/Field';
import { PageHeader } from '../components/ui/PageHeader';
import { SecretBox } from '../components/ui/SecretBox';
import { StatusBadge } from '../components/ui/StatusBadge';
import type { Tone } from '../components/ui/styles';
import { useToast } from '../components/ui/Toast';
import { Page } from '../layout/AppShell';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

const STATUS_TONE: Record<User['status'], Tone> = { active: 'success', invited: 'warning', disabled: 'neutral' };

function InviteForm({ onInvited, close }: { onInvited: (url: string) => void; close: () => void }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<User['role']>('member');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      onInvited((await api.invite(email, role)).invite_url);
      close();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} aria-label="Invite a user" className="grid gap-x-4 md:grid-cols-[1fr_200px_auto] md:items-end">
      <Field label="Email">{(id) => <Input id={id} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
      <Field label="Role">
        {(id) => (
          <Select id={id} value={role} onChange={(e) => setRole(e.target.value as User['role'])}>
            <option value="member">member</option>
            <option value="admin">admin</option>
          </Select>
        )}
      </Field>
      <Button type="submit" variant="primary" className="mb-4" busy={busy}>Create invite link</Button>
      <div className="md:col-span-3"><ErrorText>{error}</ErrorText></div>
    </form>
  );
}

/** Admins invite people (a one-time link to send them), change roles, and disable or re-invite. */
export function UsersPage() {
  const { data: users, error, reload } = useLoad(api.users);
  const { me } = useAuth();
  const { show } = useToast();
  const [link, setLink] = useState<string | null>(null);
  const change = async (u: User, patch: Parameters<typeof api.updateUser>[1], done: string) => {
    try {
      await api.updateUser(u.id, patch);
      show(done);
      reload();
    } catch (e) {
      show((e as Error).message, 'danger');
    }
  };
  const columns: Column<User>[] = [
    { key: 'email', header: 'Email', cell: (u) => <span className="font-medium text-ink-strong">{u.email}</span> },
    {
      key: 'role', header: 'Role', cell: (u) => (
        <div className="w-32"><Select aria-label={`Role of ${u.email}`} value={u.role} disabled={u.id === me.user?.id}
          onChange={(e) => void change(u, { role: e.target.value as User['role'] }, `${u.email} is now ${e.target.value}`)}>
          <option value="member">member</option>
          <option value="admin">admin</option>
        </Select></div>
      ),
    },
    { key: 'status', header: 'Status', cell: (u) => <StatusBadge tone={STATUS_TONE[u.status]}>{u.status}</StatusBadge> },
    { key: 'actions', header: <span className="sr-only">Actions</span>, className: 'text-right', cell: (u) => <UserActions user={u} self={u.id === me.user?.id} onLink={setLink} change={change} /> },
  ];
  return (
    <Page>
      <PageHeader title="Users" crumbs={[{ label: 'People' }, { label: 'Users' }]} description="Only invited people have an account. An invite is a one-time link, valid for 7 days." />
      <div className="mb-4"><CreatePanel label="Invite user">{(close) => <InviteForm close={close} onInvited={(url) => { setLink(url); reload(); }} />}</CreatePanel></div>
      {link && (
        <div className="mb-4">
          <SecretBox value={link} label="invite link">Send this one-time link to the person. It is shown only now.</SecretBox>
        </div>
      )}
      <ErrorText>{error}</ErrorText>
      <DataTable label="Users" columns={columns} rows={users} rowKey={(u) => u.id} search={(u) => `${u.email} ${u.role} ${u.status}`} />
    </Page>
  );
}

type Change = (u: User, patch: Parameters<typeof api.updateUser>[1], done: string) => Promise<void>;

function UserActions({ user, self, onLink, change }: { user: User; self: boolean; onLink: (url: string) => void; change: Change }) {
  const { show } = useToast();
  const newLink = () => void api.reinvite(user.id).then((out) => onLink(out.invite_url), (e: Error) => show(e.message, 'danger'));
  return (
    <div className="flex justify-end gap-2">
      <Button size="sm" onClick={newLink}>New link</Button>
      {user.status === 'disabled' ? (
        <Button size="sm" onClick={() => void change(user, { status: 'active' }, `${user.email} enabled`)}>Enable</Button>
      ) : (
        user.status === 'active' && !self && (
          <ConfirmButton size="sm" variant="danger" title={`Disable ${user.email}?`} confirmLabel="Disable"
            description="They are signed out everywhere and their tokens stop working. You can enable them again later."
            onConfirm={() => change(user, { status: 'disabled' }, `${user.email} disabled`)}>
            Disable
          </ConfirmButton>
        )
      )}
    </div>
  );
}
