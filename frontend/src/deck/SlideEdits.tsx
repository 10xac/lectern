import { Check, NotebookPen, Pencil, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { Slide } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Input, TextArea } from '../components/ui/Field';
import { useToast } from '../components/ui/Toast';

export type EditSlide = (n: number, change: { title?: string; notes?: string }) => Promise<void>;

/** Run an edit, toasting success; the error message comes back for the form to show. */
function useSave(edit: EditSlide) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { show } = useToast();
  const save = async (n: number, change: { title?: string; notes?: string }, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await edit(n, change);
      show(done);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, save };
}

/** The slide's title; signed-in people can rename it in place. */
export function SlideTitle({ slide, edit }: { slide: Slide; edit?: EditSlide }) {
  const [draft, setDraft] = useState<string | null>(null);
  const { busy, error, save } = useSave(edit ?? (async () => undefined));
  const title = slide.title || `Slide ${slide.n}`;
  if (draft === null || !edit) {
    return (
      <div className="flex min-w-0 items-center gap-1">
        <h2 className="truncate font-display text-lg font-medium text-ink-strong">{title}</h2>
        {edit && (
          <Button variant="ghost" size="icon" aria-label="Rename slide" onClick={() => setDraft(slide.title)}>
            <Pencil className="h-3.5 w-3.5" aria-hidden />
          </Button>
        )}
      </div>
    );
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (await save(slide.n, { title: draft }, 'Title saved')) setDraft(null);
  };
  return (
    <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-1" aria-label="Rename slide">
      <Input aria-label="Slide title" autoFocus className="max-w-md" value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && setDraft(null)} />
      <Button type="submit" variant="ghost" size="icon" aria-label="Save title" busy={busy}><Check className="h-4 w-4" aria-hidden /></Button>
      <Button variant="ghost" size="icon" aria-label="Cancel rename" onClick={() => setDraft(null)}><X className="h-4 w-4" aria-hidden /></Button>
      <ErrorText>{error}</ErrorText>
    </form>
  );
}

/** Presenter notes under the slide: shown on demand; signed-in people can edit them. */
export function NotesPanel({ slide, edit, open, onToggle }: { slide: Slide; edit?: EditSlide; open: boolean; onToggle: () => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const { busy, error, save } = useSave(edit ?? (async () => undefined));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (draft !== null && (await save(slide.n, { notes: draft }, 'Notes saved'))) setDraft(null);
  };
  return (
    <section aria-label="Presenter notes" className="rounded-lg border border-line-soft bg-surface">
      <div className="flex items-center gap-2 px-4 py-2">
        <Button variant="ghost" size="sm" aria-expanded={open} onClick={onToggle}>
          <NotebookPen className="h-4 w-4" aria-hidden /> {open ? 'Hide notes' : 'Show notes'}
        </Button>
        <span className="flex-1" />
        {open && edit && draft === null && <Button size="sm" onClick={() => setDraft(slide.notes)}>Edit notes</Button>}
      </div>
      {open && draft === null && (
        <p className="whitespace-pre-wrap border-t border-line-soft px-4 py-3 text-sm text-ink">
          {slide.notes || <span className="text-ink-muted">No presenter notes.</span>}
        </p>
      )}
      {open && draft !== null && (
        <form onSubmit={submit} className="border-t border-line-soft px-4 py-3" aria-label="Edit notes">
          <TextArea aria-label={`Notes for slide ${slide.n}`} autoFocus rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <ErrorText>{error}</ErrorText>
          <div className="mt-2 flex justify-end gap-2">
            <Button size="sm" onClick={() => setDraft(null)}>Cancel</Button>
            <Button size="sm" type="submit" variant="primary" busy={busy}>Save notes</Button>
          </div>
        </form>
      )}
    </section>
  );
}
