import { useId, useState, type FormEvent } from 'react';
import type { Slide, SlideChange } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input, TextArea } from '../components/ui/Field';
import { Drawer } from '../components/ui/Overlay';

const FIELDS = ['title', 'body', 'notes', 'html'] as const;

/** The fields that differ from the slide (all non-empty ones for a new slide). */
function changes(draft: Required<SlideChange>, slide?: Slide): SlideChange {
  const out: SlideChange = {};
  for (const f of FIELDS) if (draft[f] !== (slide?.[f] ?? '')) out[f] = draft[f];
  return out;
}

interface Props {
  /** The slide to edit; none for a new slide. */
  slide?: Slide;
  title: string;
  onSave: (change: SlideChange) => Promise<void>;
  onClose: () => void;
}

/** Edit a slide's title, body, notes and (advanced) HTML in a drawer; saves only what changed. */
export function SlideEditor({ slide, title, onSave, onClose }: Props) {
  const [draft, setDraft] = useState<Required<SlideChange>>(() => ({
    title: slide?.title ?? '', body: slide?.body ?? '', notes: slide?.notes ?? '', html: slide?.html ?? '',
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formId = useId();
  const change = changes(draft, slide);
  const dirty = Object.keys(change).length > 0;
  const set = (f: keyof SlideChange) => (e: { target: { value: string } }) => setDraft({ ...draft, [f]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await onSave(change);
      onClose();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  const footer = (
    <>
      <Button onClick={onClose}>Cancel</Button>
      <Button type="submit" form={formId} variant="primary" busy={busy} disabled={slide ? !dirty : false}>{slide ? 'Save slide' : 'Add slide'}</Button>
    </>
  );
  return (
    <Drawer title={title} onClose={onClose} footer={footer} size="lg">
      <form id={formId} onSubmit={(e) => void submit(e)} aria-label={title}>
        <Field label="Title">{(id) => <Input id={id} autoFocus value={draft.title} onChange={set('title')} />}</Field>
        <Field label="Body" hint="One point per line.">{(id) => <TextArea id={id} rows={6} value={draft.body} onChange={set('body')} />}</Field>
        <Field label="Notes">{(id) => <TextArea id={id} rows={4} value={draft.notes} onChange={set('notes')} />}</Field>
        <details className="mb-4 rounded-md border border-line-soft px-3 py-2">
          <summary className="cursor-pointer text-sm text-ink-strong">Advanced</summary>
          <Field label="HTML" className="mb-0 mt-3" hint="The slide's own markup; it replaces the text card when set.">
            {(id) => <TextArea id={id} rows={12} className="font-mono text-xs" spellCheck={false} value={draft.html} onChange={set('html')} />}
          </Field>
        </details>
        <ErrorText>{error}</ErrorText>
      </form>
    </Drawer>
  );
}
