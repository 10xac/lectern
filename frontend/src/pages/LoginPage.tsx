import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { AuthLayout } from '../layout/AuthLayout';
import { useAuth } from '../lib/auth';

/** Where to go after signing in: only a path on this site (never another origin). */
export const safeNext = (next: string | null) => (next && next.startsWith('/') && !next.startsWith('//') ? next : '/');

/** Sign in with email and password. Only invited people have an account. */
export function LoginPage() {
  const { me, signIn } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get('next'));
  if (!me.auth || me.user) return <Navigate to={next} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const out = await api.login(email, password);
      signIn(out.user, out.csrf);
      navigate(next, { replace: true });
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Sign in" subtitle="Every slide gets its own agent.">
      <form onSubmit={submit} aria-label="Sign in">
        <Field label="Email">
          {(id) => <Input id={id} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label="Password">
          {(id) => <Input id={id} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" variant="primary" size="cta" className="mt-2 w-full" busy={busy}>Sign in</Button>
        <p className="mt-4 text-xs text-ink-muted">No account? Ask an admin for an invite link.</p>
      </form>
    </AuthLayout>
  );
}
