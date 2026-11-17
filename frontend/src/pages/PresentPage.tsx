import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Deck } from '../api';
import { ChatThread } from '../deck/ChatThread';
import { DnaPanel } from '../deck/DnaPanel';
import { InfluenceDrawer } from '../deck/InfluenceDrawer';
import { SlideFrame } from '../deck/SlideFrame';
import { TraceDrawer } from '../deck/TraceDrawer';
import { useCurrentSlide } from '../deck/useDeckView';
import { Drawer } from '../components/ui/Overlay';
import { useDna } from '../hooks/useDna';
import { useSlideChat } from '../hooks/useSlideChat';
import { keyIsTaken } from '../lib/keys';
import { DeckGate } from './DeckGate';
import { PresentControls } from './PresentControls';

const NEXT = new Set(['ArrowRight', ' ', 'PageDown']);
const PREV = new Set(['ArrowLeft', 'PageUp']);

/** ←/→, space, PageUp/PageDown, Home/End move; Esc leaves; N shows the notes. */
function usePresentKeys(count: number, current: number, go: (n: number) => void, exit: () => void, toggleNotes: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (keyIsTaken(e)) return;
      const to = NEXT.has(e.key) ? current + 1 : PREV.has(e.key) ? current - 1 : e.key === 'Home' ? 1 : e.key === 'End' ? count : null;
      if (to !== null) {
        e.preventDefault();
        go(to);
      } else if (e.key === 'Escape') exit();
      else if (e.key === 'n' || e.key === 'N') toggleNotes();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [count, current, go, exit, toggleNotes]);
}

function Presenter({ deck, base }: { deck: Deck; base: string }) {
  const { current, go } = useCurrentSlide(deck.slides.length);
  const navigate = useNavigate();
  const [notes, setNotes] = useState(false);
  const [panel, setPanel] = useState<'ask' | 'dna' | null>(null);
  const [traceId, setTraceId] = useState<number | null>(null);
  const chat = useSlideChat(deck.id, current);
  const dna = useDna(deck.id);
  const slide = deck.slides.find((s) => s.n === current) ?? deck.slides[0];
  const exit = () => navigate(`${base}/${deck.id}?slide=${current}`);
  usePresentKeys(deck.slides.length, current, go, exit, () => setNotes((o) => !o));
  if (!slide) return null;
  return (
    <div className="fixed inset-0 flex flex-col bg-[#0B0B12] text-white" aria-label={`Presenting ${deck.title}`} role="region">
      <div className="flex min-h-0 flex-1 items-center justify-center p-2 sm:p-6">
        <div style={{ width: 'min(100%, calc((100vh - 7rem) * 16 / 9))' }}>
          <SlideFrame slide={slide} className="rounded-md shadow-2xl" />
          {notes && <p className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap rounded-md bg-white/10 p-3 text-sm text-white/90" aria-label="Presenter notes">{slide.notes || 'No presenter notes.'}</p>}
        </div>
      </div>
      <PresentControls n={slide.n} count={deck.slides.length} notes={notes} go={go} exit={exit}
        onNotes={() => setNotes((o) => !o)} onAsk={() => setPanel('ask')} onDna={() => setPanel('dna')} />
      {panel === 'ask' && (
        <Drawer title={`Ask slide ${slide.n}`} onClose={() => setPanel(null)} size="md">
          <div className="-mx-6 -my-4 flex h-[calc(100vh-73px)] flex-col">
            <ChatThread chat={chat} slide={slide.n} onJump={(c) => c.slide != null && go(c.slide)} onTrace={setTraceId} />
          </div>
        </Drawer>
      )}
      {panel === 'dna' && (
        <Drawer title={`DNA of slide ${slide.n}`} onClose={() => setPanel(null)} size="lg">
          <div className="-mx-6 -my-4"><DnaPanel deckId={deck.id} slide={slide.n} version={dna.version} onOpen={(id) => void dna.open(id)} /></div>
        </Drawer>
      )}
      {traceId != null && <TraceDrawer traceId={traceId} onClose={() => setTraceId(null)} />}
      {dna.drawer && (
        <InfluenceDrawer deckId={deck.id} slides={deck.slides} current={slide.n} elements={[]} picking={false} picked={null}
          onPick={() => undefined} onStopPicking={() => undefined} existing={dna.drawer.existing} readOnly onClose={dna.close} onSaved={dna.saved} />
      )}
    </div>
  );
}

/** Present mode: the slide full screen, with an Ask button so the audience can talk to the agent. */
export function PresentPage({ shared = false }: { shared?: boolean }) {
  return <DeckGate>{({ deck }) => <Presenter deck={deck} base={shared ? '/d' : '/deck'} />}</DeckGate>;
}
