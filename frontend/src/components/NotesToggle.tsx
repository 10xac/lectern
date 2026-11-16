import { useState } from 'react';

/** Presenter notes, hidden until asked for. */
export function NotesToggle({ notes }: { notes: string }) {
  const [open, setOpen] = useState(false);
  if (!notes) return <p className="muted notes-empty">No presenter notes.</p>;
  return (
    <div className="notes">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide notes' : 'Show notes'}
      </button>
      {open && <p className="notes-text">{notes}</p>}
    </div>
  );
}
