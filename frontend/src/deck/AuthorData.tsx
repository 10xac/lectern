import { Database } from 'lucide-react';
import { api, type Deck } from '../api';
import { UploadButton } from '../components/UploadButton';
import { cn } from '../lib/cn';

/** The author's data files for the deck (what att:… citations point at); a cited one is highlighted. */
export function AuthorData({ deck, highlight, canEdit, onDone }: { deck: Deck; highlight: number | null; canEdit: boolean; onDone: () => void }) {
  if (!canEdit && deck.attachments.length === 0) return null;
  return (
    <section aria-label="Author data" className="rounded-lg border border-line-soft bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <Database className="h-4 w-4 text-ink-muted" aria-hidden />
        <h3 className="mr-auto font-display text-sm font-medium text-ink-strong">Author data</h3>
        {canEdit && <UploadButton label="Add data" size="sm" accept=".txt,.md,.markdown,.csv" upload={(f) => api.uploadAttachment(deck.id, f)} onDone={onDone} />}
      </div>
      {deck.attachments.length === 0 && <p className="text-xs text-ink-muted">Add .txt, .md or .csv files the agents may cite.</p>}
      <ul className="flex flex-wrap gap-2">
        {deck.attachments.map((a) => (
          <li key={a.id} data-highlight={a.id === highlight || undefined}
            className={cn('rounded border px-2 py-1 text-xs', a.id === highlight ? 'border-warning bg-warning-soft text-warning-ink' : 'border-line-soft bg-surface-muted text-ink')}>
            {a.name} <span className="text-ink-muted">({a.chunks} parts)</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
