import { KeyRound } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { AuthLayout } from '../layout/AuthLayout';

/** A shared deck behind a password: enter it once (the browser keeps a cookie), then view. */
export function UnlockPrompt({ deckId, title, onUnlocked }: { deckId: number; title?: string; onUnlocked: () => void }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.unlock(deckId, password);
      onUnlocked();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  return (
    <AuthLayout title={title ?? 'Protected deck'} subtitle={<span className="flex items-center gap-1.5"><KeyRound className="h-4 w-4" aria-hidden /> This deck is protected by a password.</span>}>
      <form onSubmit={submit} aria-label="Unlock deck">
        <Field label="Deck password">{(id) => <Input id={id} type="password" autoFocus required value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" variant="primary" size="cta" className="mt-2 w-full" busy={busy}>Unlock</Button>
      </form>
    </AuthLayout>
  );
}
