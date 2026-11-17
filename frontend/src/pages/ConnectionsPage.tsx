import { api, type Connection } from '../api';
import { ConfirmButton } from '../components/ui/ConfirmButton';
import { DataTable, type Column } from '../components/ui/DataTable';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { PageHeader } from '../components/ui/PageHeader';
import { Page } from '../layout/AppShell';
import { useAuth } from '../lib/auth';
import { day } from '../lib/format';
import { useLoad } from '../lib/useLoad';

/** The columns of a connections table; `end` revokes one. `withEmail` adds whose it is (admins). */
export function connectionColumns(end: (c: Connection) => Promise<unknown>, withEmail = false): Column<Connection>[] {
  const cols: Column<Connection>[] = [
    { key: 'client', header: 'App', cell: (c) => <span className="font-medium text-ink-strong">{c.client}</span> },
    { key: 'created', header: 'Connected', cell: (c) => day(c.created_at) },
    { key: 'used', header: 'Last used', cell: (c) => day(c.last_used_at) },
    {
      key: 'actions', header: <span className="sr-only">Actions</span>, className: 'text-right',
      cell: (c) => (
        <ConfirmButton size="sm" variant="danger" title={`Disconnect ${c.client}?`} confirmLabel="Disconnect" description="The app loses access at once; connecting again needs a new approval." onConfirm={() => end(c)}>
          Disconnect
        </ConfirmButton>
      ),
    },
  ];
  return withEmail ? [{ key: 'email', header: 'Person', cell: (c) => c.email }, ...cols] : cols;
}

/** Apps (such as claude.ai) that this person connected over OAuth. */
export function ConnectionsPage() {
  const { me } = useAuth();
  const header = <PageHeader title="Connections" crumbs={[{ label: 'Connect' }, { label: 'Connections' }]} description="Apps you allowed to use lectern as you. Disconnect one to end its access." />;
  if (!me.auth) return <Page>{header}<EmptyState title="Login is off" description="Without accounts there is nothing to connect: MCP clients reach this server directly." /></Page>;
  return <Page>{header}<MyConnections /></Page>;
}

function MyConnections() {
  const { data, error, reload } = useLoad(api.connections);
  return (
    <>
      <ErrorText>{error}</ErrorText>
      <DataTable label="Connections" rows={data} rowKey={(c) => c.id} columns={connectionColumns((c) => api.endConnection(c.id).then(reload))}
        empty={<EmptyState title="No connected apps" description="Add lectern as a custom connector in claude.ai to see it here." />} />
    </>
  );
}
