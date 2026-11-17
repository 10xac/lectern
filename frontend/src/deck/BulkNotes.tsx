import { useState } from 'react';
import type { Slide } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { TextArea } from '../components/ui/Field';
import { Drawer } from '../components/ui/Overlay';
import { useToast } from '../components/ui/Toast';
import type { EditSlide } from './SlideEdits';

/** Edit the presenter notes of several selected slides at once; only changed ones are saved. */
export function BulkNotes({ slides, edit, onClose }: { slides: Slide[]; edit: EditSlide; onClose: () => void }) {
  const [drafts, setDrafts] = useState<Record<number, string>>(() => Object.fromEntries(slides.map((s) => [s.n, s.notes])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { show } = useToast();
  const changed = slides.filter((s) => drafts[s.n] !== s.notes);
  const save = async () => {
    setBusy(true);
    try {
      for (const s of changed) await edit(s.n, { notes: drafts[s.n] });
      show(`Notes saved on ${changed.length} slide${changed.length === 1 ? '' : 's'}`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  const footer = (
    <>
      <Button onClick={onClose}>Cancel</Button>
      <Button variant="primary" busy={busy} disabled={changed.length === 0} onClick={() => void save()}>Save notes</Button>
    </>
  );
  return (
    <Drawer title={`Notes for ${slides.length} slides`} onClose={onClose} footer={footer}>
      {slides.map((s) => (
        <label key={s.n} className="mb-4 block">
          <span className="mb-1 block text-sm text-ink-strong">
            <span className="font-semibold text-brand">{s.n}</span> {s.title || `Slide ${s.n}`}
          </span>
          <TextArea aria-label={`Notes for slide ${s.n}`} rows={4} value={drafts[s.n]} onChange={(e) => setDrafts({ ...drafts, [s.n]: e.target.value })} />
        </label>
      ))}
      <ErrorText>{error}</ErrorText>
    </Drawer>
  );
}
