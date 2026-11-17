import { ArrowLeft, Download, Plus, Presentation, Share2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { BASE, type Deck } from '../api';
import { Button } from '../components/ui/Button';
import { buttonStyles } from '../components/ui/styles';
import { VisibilityBadge } from './VisibilityBadge';

interface Props {
  deck: Deck;
  presentTo: string;
  /** Back to the deck list (signed-in view only). */
  back?: string;
  /** Offer the uploaded original file (signed-in people only). */
  canDownload?: boolean;
  onShare?: () => void;
  onInfluence?: () => void;
}

/** The deck's own top bar: title and visibility; Download original, Share, Present and + Influence. */
export function DeckBar({ deck, presentTo, back, canDownload, onShare, onInfluence }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line-soft bg-surface px-4 py-3">
      {back && (
        <Link to={back} aria-label="All decks" className={buttonStyles({ variant: 'ghost', size: 'icon' })}>
          <ArrowLeft className="h-4 w-4" aria-hidden />
        </Link>
      )}
      <h1 className="min-w-0 truncate font-display text-lg font-semibold text-ink-strong md:text-xl">{deck.title}</h1>
      <VisibilityBadge visibility={deck.visibility} />
      <span className="text-xs text-ink-muted">{deck.slides.length} slides</span>
      <span className="flex-1" />
      <div className="flex flex-wrap gap-2">
        {canDownload && deck.file_id && (
          <a href={`${BASE}/decks/${deck.id}/original`} download className={buttonStyles()}><Download className="h-4 w-4" aria-hidden /> Download original</a>
        )}
        {onShare && <Button onClick={onShare}><Share2 className="h-4 w-4" aria-hidden /> Share</Button>}
        {onInfluence && <Button onClick={onInfluence}><Plus className="h-4 w-4" aria-hidden /> Influence</Button>}
        <Link to={presentTo} className={buttonStyles({ variant: 'primary' })}><Presentation className="h-4 w-4" aria-hidden /> Present</Link>
      </div>
    </div>
  );
}
