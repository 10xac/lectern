import { FileSearch } from 'lucide-react';
import { useState } from 'react';
import { api, type Reconciled } from '../api';
import { Button } from '../components/ui/Button';
import { ConfirmButton } from '../components/ui/ConfirmButton';
import { ErrorText } from '../components/ui/ErrorText';
import { Select } from '../components/ui/Field';

/** Admins: files whose contents vanished. Relink each to a file in the store, or delete its metadata. */
export function FilesCheck() {
  const [found, setFound] = useState<Reconciled | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true);
    try {
      const r = await api.reconcile();
      setFound(r);
      setChoice(r.suggestions);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const act = async (p: Promise<unknown>) => {
    await p;
    await check();
  };
  return (
    <section aria-label="Unlinked files" className="mt-4 border-t border-line-soft pt-4">
      <div className="flex items-center gap-2">
        <Button size="sm" busy={busy} onClick={() => void check()}><FileSearch className="h-3.5 w-3.5" aria-hidden /> Check files</Button>
        {found && found.missing.length === 0 && <span className="text-xs text-ink-muted">All files are linked.</span>}
      </div>
      <ErrorText>{error}</ErrorText>
      <ul className="mt-2 space-y-2">
        {found?.missing.map((f) => (
          <li key={f.id} className="rounded-lg border border-warning-line bg-warning-soft p-3 text-sm">
            <p className="mb-2 break-all"><span className="font-mono text-xs">{f.path}</span> is missing.</p>
            <div className="flex flex-wrap gap-2">
              <Select aria-label={`New file for ${f.path}`} className="min-w-0 flex-1" value={choice[f.id] ?? ''} onChange={(e) => setChoice({ ...choice, [f.id]: e.target.value })}>
                <option value="">Relink to file…</option>
                {found.unregistered.map((p) => <option key={p}>{p}</option>)}
              </Select>
              <Button size="md" disabled={!choice[f.id]} onClick={() => void act(api.relink(f.id, choice[f.id]))}>Relink</Button>
              <ConfirmButton variant="danger" title="Delete this file's metadata?" confirmLabel="Delete metadata" description={f.path} onConfirm={() => act(api.forget(f.id))}>
                Delete metadata
              </ConfirmButton>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
