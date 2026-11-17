import { Globe, KeyRound, Lock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, type Visibility } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { Modal } from '../components/ui/Overlay';
import { CodeLine } from '../components/ui/SecretBox';
import { useToast } from '../components/ui/Toast';
import { cn } from '../lib/cn';

const OPTIONS = [
  { value: 'private', icon: Lock, label: 'Private', text: 'Only people signed in to this lectern.' },
  { value: 'public', icon: Globe, label: 'Public', text: 'Anyone with the link can view the deck and ask its agents.' },
  { value: 'password', icon: KeyRound, label: 'Password', text: 'Anyone with the link and the password.' },
] as const;

/** Who may see a deck: private, public, or public behind a password; plus the link to send. */
export function ShareDialog({ deckId, onClose, onChanged }: { deckId: number; onClose: () => void; onChanged: (v: Visibility) => void }) {
  const [visibility, setVisibility] = useState<Visibility>('private');
  const [hasPassword, setHasPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { show } = useToast();
  useEffect(() => {
    void api.sharing(deckId).then((s) => (setVisibility(s.visibility), setHasPassword(s.has_password)), (e: Error) => setError(e.message));
  }, [deckId]);
  const save = async () => {
    setBusy(true);
    try {
      const out = await api.share(deckId, visibility, visibility === 'password' ? password : undefined);
      onChanged(out.visibility);
      show(`Sharing saved: ${out.visibility}`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  const footer = <><Button onClick={onClose}>Cancel</Button><Button variant="primary" busy={busy} onClick={() => void save()}>Save</Button></>;
  return (
    <Modal title="Share deck" onClose={onClose} footer={footer}>
      <fieldset className="mb-4 space-y-2">
        <legend className="mb-2 text-sm text-ink-strong">Who can see it</legend>
        {OPTIONS.map(({ value, icon: Icon, label, text }) => (
          <label key={value} className={cn('flex cursor-pointer items-start gap-3 rounded-lg border p-3 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand/60', visibility === value ? 'border-brand bg-brand-soft/50' : 'border-line-soft hover:border-line')}>
            <input type="radio" name="visibility" className="sr-only" checked={visibility === value} onChange={() => setVisibility(value)} />
            <Icon className={cn('mt-0.5 h-4 w-4', visibility === value ? 'text-brand' : 'text-ink-muted')} aria-hidden />
            <span><span className="block font-medium text-ink-strong">{label}</span><span className="text-xs text-ink-soft">{text}</span></span>
          </label>
        ))}
      </fieldset>
      {visibility === 'password' && (
        <Field label="Password" hint={hasPassword ? 'Leave empty to keep the current password. Changing it locks out everyone who unlocked it.' : 'At least 4 characters.'}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
      )}
      {visibility !== 'private' && <><p className="mb-1 text-sm text-ink-strong">Link</p><CodeLine label="share link" value={`${window.location.origin}/d/${deckId}`} /></>}
      <ErrorText>{error}</ErrorText>
    </Modal>
  );
}
