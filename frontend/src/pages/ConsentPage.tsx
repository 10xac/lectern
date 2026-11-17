import { ShieldCheck } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { AuthLayout } from '../layout/AuthLayout';
import { useAuth } from '../lib/auth';
import { browser } from '../lib/browser';
import { useLoad } from '../lib/useLoad';

/** The OAuth consent step: an app (such as claude.ai) asks to use lectern as the signed-in person. */
export function ConsentPage() {
  const { me } = useAuth();
  const location = useLocation();
  const txn = useSearchParams()[0].get('txn') ?? '';
  if (me.auth && !me.user) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }
  return (
    <AuthLayout title="Connect an app">
      {txn ? <Consent txn={txn} email={me.user?.email ?? 'the local user'} /> : <Problem text="This link has no sign-in request in it. Start connecting again from the app." />}
    </AuthLayout>
  );
}

function Problem({ text }: { text: string }) {
  return (
    <EmptyState
      title="This request cannot continue"
      description={text}
      action={<Link className="text-brand" to="/">Go to lectern</Link>}
    />
  );
}

function Consent({ txn, email }: { txn: string; email: string }) {
  const { data, error } = useLoad(useCallback(() => api.consent(txn), [txn]));
  const [busy, setBusy] = useState<'approve' | 'deny' | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  if (error) return <Problem text={`${error.charAt(0).toUpperCase()}${error.slice(1)}.`} />;
  if (!data) return <p className="text-ink-muted" role="status">Loading…</p>;
  const decide = async (approve: boolean) => {
    setBusy(approve ? 'approve' : 'deny');
    try {
      browser.assign((await api.completeConsent(txn, approve)).redirect_to);
    } catch (e) {
      setFailed((e as Error).message);
      setBusy(null);
    }
  };
  return (
    <section aria-label="Consent">
      <div className="mb-4 flex items-center gap-3 rounded-lg border border-line-soft bg-surface-muted p-4">
        <ShieldCheck className="h-8 w-8 shrink-0 text-brand" aria-hidden />
        <p className="text-sm text-ink">
          <strong className="text-ink-strong">{data.client}</strong> wants to use lectern as <strong className="text-ink-strong">{email}</strong>.
        </p>
      </div>
      <ul className="mb-4 list-disc pl-5 text-sm text-ink-soft">
        <li>Read your decks, ask their agents and add DNA, as you.</li>
        {data.redirect_host && <li>You will be sent back to <span className="font-mono">{data.redirect_host}</span>.</li>}
        <li>You can end this connection any time under Connections.</li>
      </ul>
      <ErrorText>{failed}</ErrorText>
      <div className="mt-4 flex gap-2">
        <Button variant="primary" size="cta" className="flex-1" busy={busy === 'approve'} disabled={busy !== null} onClick={() => void decide(true)}>Approve</Button>
        <Button size="cta" className="flex-1" busy={busy === 'deny'} disabled={busy !== null} onClick={() => void decide(false)}>Deny</Button>
      </div>
    </section>
  );
}
