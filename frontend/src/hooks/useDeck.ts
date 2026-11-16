import { useCallback, useEffect, useState } from 'react';
import { api, type Deck } from '../api';

/** Load one deck; `reload` fetches it again (after an attachment upload). */
export function useDeck(deckId: number) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .getDeck(deckId)
      .then((d) => live && setDeck(d))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [deckId, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { deck, error, reload };
}
