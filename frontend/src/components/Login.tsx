import { useState, type FormEvent } from 'react';
import { api, type User } from '../api';

/** The invite token from a link like https://host/#invite=<token> (the fragment never reaches a server). */
export const inviteToken = (hash: string) => /[#&]invite=([\w-]+)/.exec(hash)?.[1] ?? null;

interface Props {
  invite: string | null;
  onIn: (user: User, csrf: string) => void;
}

/** Sign in, or (from an invite link) choose a password. Only invited people have an account. */
export function Login({ invite, onIn }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const out = invite ? await api.acceptInvite(invite, password) : await api.login(email, password);
      if (invite) window.history.replaceState(null, '', window.location.pathname);
      onIn(out.user, out.csrf);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <form className="login" onSubmit={submit} aria-label={invite ? 'Choose a password' : 'Sign in'}>
      <h1>lectern</h1>
      {invite ? (
        <p>You were invited. Choose a password (at least 12 characters).</p>
      ) : (
        <input aria-label="Email" type="email" autoComplete="username" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      )}
      <input aria-label="Password" type="password" required value={password}
        autoComplete={invite ? 'new-password' : 'current-password'} onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="error">{error}</p>}
      <button type="submit">{invite ? 'Set password' : 'Sign in'}</button>
    </form>
  );
}
