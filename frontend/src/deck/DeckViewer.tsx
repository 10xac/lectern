import { ChevronLeft, ChevronRight, NotebookPen, Plus, X } from 'lucide-react';
import { useState } from 'react';
import type { Deck, Visibility } from '../api';
import { Button } from '../components/ui/Button';
import { useSlideChat } from '../hooks/useSlideChat';
import { AuthorData } from './AuthorData';
import { BulkNotes } from './BulkNotes';
import { DeckBar } from './DeckBar';
import { elementsOf, InfluenceDrawer } from './InfluenceDrawer';
import { ShareDialog } from './ShareDialog';
import { SidePanel } from './SidePanel';
import { NotesPanel, SlideTitle, type EditSlide } from './SlideEdits';
import { SlideFrame } from './SlideFrame';
import { SlideRail } from './SlideRail';
import { TraceDrawer } from './TraceDrawer';
import { useDeckView } from './useDeckView';

export interface ViewerProps {
  deck: Deck;
  /** "/deck" inside the app, "/d" for a shared link. */
  base: string;
  canEdit: boolean;
  admin: boolean;
  author?: string;
  editSlide: EditSlide;
  reload: () => void;
  onVisibility: (v: Visibility) => void;
}

/** One deck: the slide rail, the slide with its notes, and the Ask / Ask the deck / DNA panel. */
export function DeckViewer(props: ViewerProps) {
  const { deck, base, canEdit } = props;
  const view = useDeckView(deck);
  const slideChat = useSlideChat(deck.id, view.current);
  const deckChat = useSlideChat(deck.id, null);
  const [share, setShare] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [bulkNotes, setBulkNotes] = useState(false);
  const slide = deck.slides.find((s) => s.n === view.current) ?? deck.slides[0];
  const edit = canEdit ? props.editSlide : undefined;
  if (!slide) return <p className="p-8 text-ink-muted">This deck has no slides.</p>;
  return (
    <div className="flex flex-col lg:h-[calc(100vh-64px)]">
      <DeckBar deck={deck} presentTo={`${base}/${deck.id}/present?slide=${slide.n}`} back={base === '/deck' ? '/' : undefined}
        onShare={canEdit ? () => setShare(true) : undefined} onInfluence={canEdit ? () => void view.dna.open() : undefined} />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="shrink-0 border-b border-line-soft bg-surface lg:w-56 lg:overflow-y-auto lg:border-b-0 lg:border-r xl:w-60">
          {canEdit && view.selected.length > 0 && (
            <SelectionBar count={view.selected.length} onInfluence={() => void view.dna.open(undefined, view.selected)} onNotes={() => setBulkNotes(true)} onClear={() => view.setSelected([])} />
          )}
          <SlideRail slides={deck.slides} current={slide.n} onSelect={view.go} selected={view.selected} onToggle={view.toggle} selectable={canEdit} />
        </aside>
        <div className="min-w-0 flex-1 overflow-y-auto bg-surface-muted p-4 lg:p-6">
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="flex items-center gap-2">
              <SlideTitle key={slide.n} slide={slide} edit={edit} />
              <span className="flex-1" />
              <Button variant="ghost" size="icon" aria-label="Previous slide" disabled={slide.n <= 1} onClick={() => view.go(slide.n - 1)}><ChevronLeft className="h-4 w-4" aria-hidden /></Button>
              <span className="text-sm tabular-nums text-ink-muted" aria-live="polite">{slide.n} / {deck.slides.length}</span>
              <Button variant="ghost" size="icon" aria-label="Next slide" disabled={slide.n >= deck.slides.length} onClick={() => view.go(slide.n + 1)}><ChevronRight className="h-4 w-4" aria-hidden /></Button>
            </div>
            <SlideFrame slide={slide} picking={view.dna.picking} className="rounded-lg shadow-card" />
            <NotesPanel key={slide.n} slide={slide} edit={edit} open={notesOpen} onToggle={() => setNotesOpen((o) => !o)} />
            <AuthorData deck={deck} highlight={view.highlight} canEdit={canEdit} onDone={props.reload} />
          </div>
        </div>
        <aside className="flex min-h-[560px] shrink-0 flex-col border-t border-line-soft bg-surface lg:min-h-0 lg:w-[380px] lg:border-l lg:border-t-0 xl:w-[420px]">
          <SidePanel deckId={deck.id} slide={slide.n} tab={view.tab} onTab={view.setTab} onJump={view.jump} onTrace={view.setTraceId}
            onOpenInfluence={(id) => void view.dna.open(id)} dnaVersion={view.dna.version} admin={props.admin} slideChat={slideChat} deckChat={deckChat} />
        </aside>
      </div>
      <Overlays {...props} view={view} slideN={slide.n} share={share} setShare={setShare} bulkNotes={bulkNotes} setBulkNotes={setBulkNotes} />
    </div>
  );
}

function SelectionBar({ count, onInfluence, onNotes, onClear }: { count: number; onInfluence: () => void; onNotes: () => void; onClear: () => void }) {
  return (
    <div className="sticky top-0 z-10 flex flex-wrap items-center gap-1 border-b border-line-soft bg-brand-soft px-3 py-2 text-xs" role="toolbar" aria-label="Selected slides">
      <span className="mr-auto font-medium text-brand-strong">{count} selected</span>
      <Button size="sm" variant="ghost" onClick={onInfluence}><Plus className="h-3.5 w-3.5" aria-hidden /> Add influence to selected</Button>
      <Button size="sm" variant="ghost" onClick={onNotes}><NotebookPen className="h-3.5 w-3.5" aria-hidden /> Edit notes</Button>
      <Button size="sm" variant="ghost" aria-label="Clear selection" onClick={onClear}><X className="h-3.5 w-3.5" aria-hidden /></Button>
    </div>
  );
}

type OverlayProps = ViewerProps & {
  view: ReturnType<typeof useDeckView>;
  slideN: number;
  share: boolean;
  setShare: (open: boolean) => void;
  bulkNotes: boolean;
  setBulkNotes: (open: boolean) => void;
};

/** The deck view's drawers and dialogs. */
function Overlays({ deck, view, slideN, share, setShare, bulkNotes, setBulkNotes, canEdit, author, editSlide, onVisibility }: OverlayProps) {
  const { dna } = view;
  const slide = deck.slides.find((s) => s.n === slideN);
  return (
    <>
      {view.traceId != null && <TraceDrawer traceId={view.traceId} onClose={() => view.setTraceId(null)} />}
      {share && <ShareDialog deckId={deck.id} onClose={() => setShare(false)} onChanged={onVisibility} />}
      {bulkNotes && <BulkNotes slides={deck.slides.filter((s) => view.selected.includes(s.n))} edit={editSlide} onClose={() => setBulkNotes(false)} />}
      {dna.drawer && (
        <InfluenceDrawer
          key={dna.drawer.existing?.id ?? `new-${slideN}-${dna.drawer.slides?.join(',') ?? ''}`}
          deckId={deck.id} slides={deck.slides} current={slideN} scoped={dna.drawer.slides} elements={elementsOf(slide?.html ?? null)}
          picking={dna.picking} picked={dna.picked} onPick={dna.pick} onStopPicking={dna.stopPicking}
          existing={dna.drawer.existing} readOnly={!canEdit} author={author} onClose={dna.close} onSaved={dna.saved}
        />
      )}
    </>
  );
}
