import { useState, type FormEvent } from 'react';
import { api, type AccessToken } from '../api';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ConfirmButton } from '../components/ui/ConfirmButton';
import { CreatePanel } from '../components/ui/CreatePanel';
import { DataTable, type Column } from '../components/ui/DataTable';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { PageHeader } from '../components/ui/PageHeader';
import { CodeLine, SecretBox } from '../components/ui/SecretBox';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Page } from '../layout/AppShell';
import { useAuth } from '../lib/auth';
import { day } from '../lib/format';
import { useLoad } from '../lib/useLoad';

function NewToken({ onSecret, close }: { onSecret: (secret: string) => void; close: () => void }) {
  const [name, setName] = useState('');
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      onSecret((await api.createToken(name, days)).secret);
      close();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return (
    <form onSubmit={submit} aria-label="New token" className="grid gap-x-4 md:grid-cols-[1fr_140px_auto] md:items-end">
      <Field label="Name">{(id) => <Input id={id} required placeholder="e.g. Claude Code on my laptop" value={name} onChange={(e) => setName(e.target.value)} />}</Field>
      <Field label="Valid for (days)">{(id) => <Input id={id} type="number" min={1} max={90} required value={days} onChange={(e) => setDays(Number(e.target.value))} />}</Field>
      <Button type="submit" variant="primary" className="mb-4">Create token</Button>
      <div className="md:col-span-3"><ErrorText>{error}</ErrorText></div>
    </form>
  );
}

/** How to use lectern from Claude Code (with a token) and from claude.ai (OAuth, no token). */
export function ConnectHelp({ secret }: { secret?: string }) {
  const origin = window.location.origin;
  return (
    <Card title="Connect an AI client" className="mt-6">
      <p className="mb-2 text-sm text-ink-strong">Claude Code</p>
      <CodeLine label="Claude Code command" value={`claude mcp add --transport http lectern ${origin}/mcp/ --header "Authorization: Bearer ${secret ?? '<your token>'}"`} />
      <p className="mb-2 mt-4 text-sm text-ink-strong">claude.ai</p>
      <p className="mb-2 text-sm text-ink-soft">Settings → Connectors → Add custom connector, with this URL. It signs in via OAuth: no token needed.</p>
      <CodeLine label="connector URL" value={`${origin}/mcp`} />
    </Card>
  );
}

/** Personal access tokens for MCP: each secret is shown once, then only its name and dates. */
export function TokensPage() {
  const { me } = useAuth();
  const header = <PageHeader title="MCP tokens" crumbs={[{ label: 'Connect' }, { label: 'MCP tokens' }]} description="A token lets an MCP client such as Claude Code use lectern as you." />;
  if (!me.auth) {
    return <Page>{header}<EmptyState title="Login is off" description="This server has one local user and no accounts, so MCP clients need no token." /><ConnectHelp /></Page>;
  }
  return <Page>{header}<MyTokens /></Page>;
}

function MyTokens() {
  const [secret, setSecret] = useState<string | null>(null);
  const { data, error, reload } = useLoad(api.tokens);
  const columns: Column<AccessToken>[] = [
    { key: 'name', header: 'Name', cell: (t) => <span className="font-medium text-ink-strong">{t.name}</span> },
    { key: 'created', header: 'Created', cell: (t) => day(t.created_at) },
    { key: 'expires', header: 'Expires', cell: (t) => day(t.expires_at) },
    { key: 'used', header: 'Last used', cell: (t) => day(t.last_used_at) },
    {
      key: 'actions', header: <span className="sr-only">Actions</span>, className: 'text-right',
      cell: (t) => t.revoked_at ? <StatusBadge>revoked</StatusBadge> : (
        <ConfirmButton size="sm" variant="danger" title={`Revoke "${t.name}"?`} confirmLabel="Revoke" description="Clients using this token stop working at once." onConfirm={() => api.revokeToken(t.id).then(reload)}>Revoke</ConfirmButton>
      ),
    },
  ];
  return (
    <>
      <div className="mb-4"><CreatePanel label="New token">{(close) => <NewToken close={close} onSecret={(s) => { setSecret(s); reload(); }} />}</CreatePanel></div>
      {secret && <div className="mb-4"><SecretBox value={secret} label="token">Copy it now: it is not shown again.</SecretBox></div>}
      <ErrorText>{error}</ErrorText>
      <DataTable label="Tokens" columns={columns} rows={data} rowKey={(t) => t.id} empty={<EmptyState title="No tokens yet" description="Create one for each MCP client you use." />} />
      <ConnectHelp secret={secret ?? undefined} />
    </>
  );
}
