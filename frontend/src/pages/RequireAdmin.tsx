import type { ReactNode } from 'react';
import { EmptyState } from '../components/ui/EmptyState';
import { Page } from '../layout/AppShell';
import { useAuth } from '../lib/auth';

/** Admin pages show a short explanation to members instead of failing requests. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  if (isAdmin) return <>{children}</>;
  return (
    <Page>
      <EmptyState title="Admins only" description="Ask an admin of this lectern if you need this page." />
    </Page>
  );
}
