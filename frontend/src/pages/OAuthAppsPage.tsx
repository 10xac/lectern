import { api, type OAuthClient } from '../api';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { DataTable, type Column } from '../components/ui/DataTable';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useToast } from '../components/ui/Toast';
import { Page } from '../layout/AppShell';
import { day } from '../lib/format';
import { useLoad } from '../lib/useLoad';
import { connectionColumns } from './ConnectionsPage';

function hostOf(uri: string): string {
  try {
    return new URL(uri).host || uri;
  } catch {
    return uri;
  }
}

/** Admins see every registered OAuth app (disable or enable it) and every live connection. */
export function OAuthAppsPage() {
  const clients = useLoad(api.oauthClients);
  const grants = useLoad(api.allConnections);
  const { show } = useToast();
  const toggle = (c: OAuthClient) =>
    void api.setClientDisabled(c.id, !c.disabled).then(() => {
      show(`${c.name} ${c.disabled ? 'enabled' : 'disabled'}`);
      clients.reload();
    }, (e: Error) => show(e.message, 'danger'));
  const columns: Column<OAuthClient>[] = [
    { key: 'name', header: 'App', cell: (c) => <span className="font-medium text-ink-strong">{c.name}</span> },
    { key: 'redirect', header: 'Redirects to', cell: (c) => <span className="break-all font-mono text-xs">{c.redirect_uris.map(hostOf).join(', ')}</span> },
    { key: 'created', header: 'Registered', cell: (c) => day(c.created_at) },
    { key: 'status', header: 'Status', cell: (c) => <StatusBadge tone={c.disabled ? 'neutral' : 'success'}>{c.disabled ? 'disabled' : 'enabled'}</StatusBadge> },
    { key: 'actions', header: <span className="sr-only">Actions</span>, className: 'text-right', cell: (c) => <Button size="sm" variant={c.disabled ? 'default' : 'danger'} onClick={() => toggle(c)}>{c.disabled ? 'Enable' : 'Disable'}</Button> },
  ];
  return (
    <Page>
      <PageHeader title="OAuth apps" crumbs={[{ label: 'Connect' }, { label: 'OAuth apps' }]} description="MCP clients register themselves when someone connects them. Disable one to refuse it everywhere." />
      <ErrorText>{clients.error}</ErrorText>
      <DataTable label="OAuth apps" columns={columns} rows={clients.data} rowKey={(c) => c.id} empty={<EmptyState title="No apps registered yet" />} />
      <Card title="All connections" className="mt-6" bodyClassName="p-4">
        <ErrorText>{grants.error}</ErrorText>
        <DataTable label="All connections" rows={grants.data} rowKey={(c) => c.id} columns={connectionColumns((c) => api.endAnyConnection(c.id).then(grants.reload), true)} empty={<EmptyState title="Nobody has connected an app" />} />
      </Card>
    </Page>
  );
}
