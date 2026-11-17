import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { AuthLayout } from '../layout/AuthLayout';
import { useAuth } from '../lib/auth';

/** The invite token from a link like https://host/#invite=<token> (the fragment never reaches a server). */
export const inviteToken = (hash: string) => /[#&]invite=([\w-]+)/.exec(hash)?.[1] ?? null;

export const MIN_PASSWORD = 12;

/** From an invite link: choose a password (at least 12 characters) and sign in. */
export function AcceptInvitePage() {
  const { signIn } = useAuth();
  const token = inviteToken(useLocation().hash);
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!token) {
    return (
      <AuthLayout title="Invite link">
        <EmptyState title="This link has no invite in it" description="Open the full link you were sent, or ask an admin for a new one." action={<Link className="text-brand" to="/login">Go to sign in</Link>} />
      </AuthLayout>
    );
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters.`);
    if (password !== again) return setError('The two passwords differ.');
    setBusy(true);
    try {
      const out = await api.acceptInvite(token, password);
      signIn(out.user, out.csrf);
      navigate('/', { replace: true });
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Welcome to lectern" subtitle="You were invited. Choose a password to finish.">
      <form onSubmit={submit} aria-label="Choose a password">
        <Field label="Password" hint={`At least ${MIN_PASSWORD} characters.`}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label="Repeat password">
          {(id) => <Input id={id} type="password" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.target.value)} />}
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" variant="primary" size="cta" className="mt-2 w-full" busy={busy}>Set password</Button>
      </form>
    </AuthLayout>
  );
}
