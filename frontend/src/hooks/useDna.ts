import { useCallback, useEffect, useState } from 'react';
import { api, type Influence } from '../api';

/** Element ids the slide may report: ingest's `data-lectern-id` values, nothing else. */
export const PICKABLE_ID = /^[\w.-]{1,200}$/;

interface DrawerState {
  existing: Influence | null;
  /** For a new influence: the slides it starts scoped to (a rail selection). */
  slides?: number[];
}

/**
 * The DNA side of a deck view: the drawer (new or editing one influence), picking an element on the
 * slide, and a version number that tells the DNA panel to reload after a save.
 */
export function useDna(deckId: number) {
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!picking) return;
    // The sandboxed slide posts {lecternPick: id} when an element is clicked in pick mode.
    const onMessage = (e: MessageEvent) => {
      const id = (e.data as { lecternPick?: unknown } | null)?.lecternPick;
      if (typeof id === 'string' && PICKABLE_ID.test(id)) {
        setPicked(id);
        setPicking(false);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [picking]);

  const open = useCallback(
    async (influenceId?: string, slides?: number[]) => {
      setPicked(null);
      if (!influenceId) return setDrawer({ existing: null, slides });
      const all = await api.influences(deckId);
      setDrawer({ existing: all.find((i) => i.id === influenceId) ?? null });
    },
    [deckId],
  );
  const close = useCallback(() => {
    setDrawer(null);
    setPicking(false);
  }, []);
  const saved = useCallback(() => {
    close();
    setVersion((v) => v + 1);
  }, [close]);
  return {
    drawer, open, close, saved, picking, picked, version,
    pick: () => setPicking(true),
    stopPicking: () => setPicking(false),
  };
}
