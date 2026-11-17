import { Bot, Dna, MessagesSquare } from 'lucide-react';
import type { Citation } from '../api';
import type { useSlideChat } from '../hooks/useSlideChat';
import { SectionTabs } from '../components/ui/SectionTabs';
import { ChatThread } from './ChatThread';
import { DnaPanel } from './DnaPanel';
import type { PanelTab } from './useDeckView';

interface Props {
  deckId: number;
  slide: number;
  tab: PanelTab;
  onTab: (tab: PanelTab) => void;
  onJump: (citation: Citation) => void;
  onTrace: (traceId: number) => void;
  onOpenInfluence: (id: string) => void;
  dnaVersion: number;
  admin: boolean;
  slideChat: ReturnType<typeof useSlideChat>;
  deckChat: ReturnType<typeof useSlideChat>;
}

/** The right-hand panel: ask this slide, ask the whole deck, or read the DNA. */
export function SidePanel({ deckId, slide, tab, onTab, onJump, onTrace, onOpenInfluence, dnaVersion, admin, slideChat, deckChat }: Props) {
  const tabs = [
    { key: 'ask' as const, label: <span className="flex items-center gap-1.5"><Bot className="h-4 w-4" aria-hidden />Ask slide {slide}</span> },
    { key: 'deck' as const, label: <span className="flex items-center gap-1.5"><MessagesSquare className="h-4 w-4" aria-hidden />Ask the deck</span> },
    { key: 'dna' as const, label: <span className="flex items-center gap-1.5"><Dna className="h-4 w-4" aria-hidden />DNA</span> },
  ];
  return (
    <>
      <SectionTabs label="Slide panel" tabs={tabs} value={tab} onChange={onTab} className="shrink-0 px-4" />
      <div role="tabpanel" aria-label={tab === 'dna' ? 'DNA' : tab === 'deck' ? 'Ask the deck' : `Ask slide ${slide}`} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {tab === 'ask' && <ChatThread chat={slideChat} slide={slide} onJump={onJump} onTrace={onTrace} />}
        {tab === 'deck' && <ChatThread chat={deckChat} slide={null} onJump={onJump} onTrace={onTrace} />}
        {tab === 'dna' && <DnaPanel deckId={deckId} slide={slide} version={dnaVersion} onOpen={onOpenInfluence} admin={admin} />}
      </div>
    </>
  );
}
