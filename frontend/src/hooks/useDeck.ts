import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, type Deck, type Slide, type SlideChange } from '../api';

/** Load one deck. `status` is the HTTP status of a failed load (401: not allowed to see it yet). */
export function useDeck(deckId: number) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    api.getDeck(deckId).then(
      (d) => live && (setDeck(d), setError(null)),
      (e: Error) => live && setError({ message: e.message, status: e instanceof ApiError ? e.status : 0 }),
    );
    return () => {
      live = false;
    };
  }, [deckId, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  /** Edit a slide on the server, then show the change without a reload. */
  const editSlide = useCallback(
    async (n: number, change: SlideChange) => {
      await api.updateSlide(deckId, n, change);
      setDeck((d) => d && { ...d, slides: d.slides.map((s): Slide => (s.n === n ? { ...s, ...change } : s)) });
    },
    [deckId],
  );
  return { deck, error, reload, editSlide, setDeck };
}
