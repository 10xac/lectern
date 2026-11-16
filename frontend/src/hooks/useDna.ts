import { useCallback, useEffect, useState } from 'react';
import { api, type Influence } from '../api';

/**
 * The DNA side of a deck view: the drawer (new or editing one influence), picking an element on the
 * slide, and a version number that tells the DNA panel to reload after a save.
 */
export function useDna(deckId: number) {
  const [drawer, setDrawer] = useState<{ existing: Influence | null } | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    // The sandboxed slide posts {lecternPick: id} when an element is clicked in pick mode.
    const onMessage = (e: MessageEvent) => {
      const id = (e.data as { lecternPick?: unknown } | null)?.lecternPick;
      if (picking && typeof id === 'string' && /^[\w.-]{1,200}$/.test(id)) {
        setPicked(id);
        setPicking(false);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [picking]);

  const open = useCallback(
    async (influenceId?: string) => {
      setPicked(null);
      if (!influenceId) return setDrawer({ existing: null });
      const all = await api.influences(deckId);
      setDrawer({ existing: all.find((i) => i.id === influenceId) ?? null });
    },
    [deckId],
  );
  const close = () => {
    setDrawer(null);
    setPicking(false);
  };
  const saved = () => {
    close();
    setVersion((v) => v + 1);
  };
  return { drawer, open, close, saved, picking, pick: () => setPicking(true), picked, version };
}
