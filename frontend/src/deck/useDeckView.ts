import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Citation, Deck } from '../api';
import { useDna } from '../hooks/useDna';
import { keyIsTaken } from '../lib/keys';

export type PanelTab = 'ask' | 'deck' | 'dna';

/** The current slide, kept in `?slide=` so a link (or a reload) opens the same slide. */
export function useCurrentSlide(count: number) {
  const [params, setParams] = useSearchParams();
  const current = Math.min(Math.max(Number(params.get('slide')) || 1, 1), Math.max(count, 1));
  // `total` overrides the slide count for a deck that just changed (e.g. go to a slide just added).
  const go = useCallback(
    (n: number, total = count) => setParams((p) => {
      const next = new URLSearchParams(p);
      next.set('slide', String(Math.min(Math.max(n, 1), Math.max(total, 1))));
      return next;
    }, { replace: true }),
    [count, setParams],
  );
  return { current, go };
}

/** Everything a deck view tracks besides the deck itself: slide, selection, panel, drawers. */
export function useDeckView(deck: Deck) {
  const { current, go } = useCurrentSlide(deck.slides.length);
  const [selected, setSelected] = useState<number[]>([]);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [tab, setTab] = useState<PanelTab>('ask');
  const [traceId, setTraceId] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const dna = useDna(deck.id);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (keyIsTaken(e)) return;
      if (e.key === 'ArrowRight') go(current + 1);
      if (e.key === 'ArrowLeft') go(current - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [current, go]);

  const toggle = (n: number, range: boolean) => {
    if (range && anchor !== null) {
      const [lo, hi] = anchor < n ? [anchor, n] : [n, anchor];
      const span = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
      setSelected((s) => [...new Set([...s, ...span])].sort((a, b) => a - b));
    } else {
      setSelected((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n].sort((a, b) => a - b)));
    }
    setAnchor(n);
  };
  const jump = (c: Citation) => {
    if (c.slide != null) go(c.slide);
    setHighlight(c.attachment);
    if (c.influence) void dna.open(c.influence);
    if (c.file) setTab('dna');
  };
  return { current, go, selected, setSelected, toggle, tab, setTab, traceId, setTraceId, highlight, jump, dna };
}
