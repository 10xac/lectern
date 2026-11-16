import { useEffect, useState } from 'react';
import { api, type DeckSummary } from '../api';

const SOURCE_LABEL = { html: 'HTML artifact', pptx: 'PowerPoint', gslides: 'Google Slides' } as const;

/** Every deck; `version` changes after an upload so the list reloads. */
export function DeckList({ version, onOpen }: { version: number; onOpen: (id: number) => void }) {
  const [decks, setDecks] = useState<DeckSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .listDecks()
      .then((d) => live && setDecks(d))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [version]);

  if (error) return <p className="error">{error}</p>;
  if (!decks) return <p className="muted">Loading decks…</p>;
  if (decks.length === 0) return <p className="muted">No decks yet. Upload one, or run make seed.</p>;
  return (
    <ul className="deck-list">
      {decks.map((d) => (
        <li key={d.id}>
          <button type="button" onClick={() => onOpen(d.id)}>
            {d.title}
          </button>
          <span className="muted"> {SOURCE_LABEL[d.source]}</span>
        </li>
      ))}
    </ul>
  );
}
