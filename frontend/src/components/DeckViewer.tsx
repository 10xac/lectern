import { useEffect, useState } from 'react';
import { api, type Citation } from '../api';
import { useDeck } from '../hooks/useDeck';
import { useDna } from '../hooks/useDna';
import { DnaPanel } from './DnaPanel';
import { elementsOf, InfluenceDrawer } from './InfluenceDrawer';
import { SlideChat } from './SlideChat';
import { SlidePane } from './SlidePane';
import { SlideRail } from './SlideRail';
import { TracePanel } from './TracePanel';
import { Upload } from './Upload';
import type { Deck } from '../api';

/** One deck: the slide rail, the current slide, its chat, the author's data and the trace drawer. */
export function DeckViewer({ deckId }: { deckId: number }) {
  const { deck, error, reload } = useDeck(deckId);
  const [current, setCurrent] = useState(1);
  const [traceId, setTraceId] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [showDna, setShowDna] = useState(false);
  const dna = useDna(deckId);
  const count = deck?.slides.length ?? 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === 'ArrowRight') setCurrent((n) => Math.min(n + 1, count));
      if (e.key === 'ArrowLeft') setCurrent((n) => Math.max(n - 1, 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [count]);

  if (error) return <p className="error">{error}</p>;
  if (!deck) return <p className="muted">Loading deck…</p>;
  const slide = deck.slides.find((s) => s.n === current) ?? deck.slides[0];

  const jump = (c: Citation) => {
    if (c.slide != null) setCurrent(c.slide);
    setHighlight(c.attachment);
    if (c.influence) void dna.open(c.influence);
    if (c.file) setShowDna(true);
  };

  return (
    <div className="viewer">
      <SlideRail slides={deck.slides} current={slide.n} onSelect={setCurrent} />
      <main>
        <header className="deck-head">
          <h1>{deck.title}</h1>
          <button type="button" aria-pressed={showDna} onClick={() => setShowDna(!showDna)}>DNA</button>
          <button type="button" onClick={() => void dna.open()}>+ New influence</button>
        </header>
        <SlidePane slide={slide} picking={dna.picking} />
        {showDna && <DnaPanel deckId={deckId} slide={slide.n} version={dna.version} onOpen={(id) => void dna.open(id)} />}
        <AuthorData deck={deck} highlight={highlight} onDone={reload} />
      </main>
      <SlideChat deckId={deckId} slide={slide.n} onJump={jump} onTrace={setTraceId} />
      {traceId != null && <TracePanel traceId={traceId} onClose={() => setTraceId(null)} />}
      {dna.drawer && (
        <InfluenceDrawer
          key={dna.drawer.existing?.id ?? `new-${slide.n}`}
          deckId={deckId} slides={deck.slides} current={slide.n} elements={elementsOf(slide.html)}
          picked={dna.picked} onPick={dna.pick} existing={dna.drawer.existing} onClose={dna.close} onSaved={dna.saved}
        />
      )}
    </div>
  );
}

/** The author's data files for the deck, with an upload button; a cited one is highlighted. */
function AuthorData({ deck, highlight, onDone }: { deck: Deck; highlight: number | null; onDone: () => void }) {
  return (
    <section className="attachments" aria-label="Author data">
      <h2>Author data</h2>
      <ul>
        {deck.attachments.map((a) => (
          <li key={a.id} className={a.id === highlight ? 'highlight' : undefined}>
            {a.name} <span className="muted">({a.chunks} parts)</span>
          </li>
        ))}
      </ul>
      <Upload
        label="Add data (.txt, .md, .csv)"
        accept=".txt,.md,.markdown,.csv"
        upload={(f) => api.uploadAttachment(deck.id, f)}
        onDone={onDone}
      />
    </section>
  );
}
