import { ChevronLeft, ChevronRight, Dna, Maximize, MessageCircleQuestion, NotebookPen, X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

interface Props {
  n: number;
  count: number;
  notes: boolean;
  go: (n: number) => void;
  exit: () => void;
  onNotes: () => void;
  onAsk: () => void;
  onDna: () => void;
}

function Control({ label, onClick, children, pressed, disabled }: { label: string; onClick: () => void; children: ReactNode; pressed?: boolean; disabled?: boolean }) {
  return (
    <button type="button" aria-label={label} title={label} aria-pressed={pressed} disabled={disabled} onClick={onClick}
      className={cn('flex h-9 min-w-9 items-center justify-center gap-1.5 rounded px-2 text-sm text-white/80 hover:bg-white/10 hover:text-white disabled:opacity-30', pressed && 'bg-white/15 text-white')}>
      {children}
    </button>
  );
}

const fullScreen = () => {
  if (document.fullscreenElement) void document.exitFullscreen?.();
  else void document.documentElement.requestFullscreen?.().catch(() => undefined);
};

/** Present mode's bar: exit, previous/next with the counter, notes, DNA, full screen; and the Ask button. */
export function PresentControls({ n, count, notes, go, exit, onNotes, onAsk, onDna }: Props) {
  return (
    <>
      <div className="flex h-14 shrink-0 items-center gap-1 border-t border-white/10 px-3" role="toolbar" aria-label="Presentation controls">
        <Control label="Exit presentation (Esc)" onClick={exit}><X className="h-4 w-4" aria-hidden /></Control>
        <span className="flex-1" />
        <Control label="Previous slide" disabled={n <= 1} onClick={() => go(n - 1)}><ChevronLeft className="h-5 w-5" aria-hidden /></Control>
        <span className="min-w-16 text-center text-sm tabular-nums text-white/80" aria-live="polite" aria-label={`Slide ${n} of ${count}`}>{n} / {count}</span>
        <Control label="Next slide" disabled={n >= count} onClick={() => go(n + 1)}><ChevronRight className="h-5 w-5" aria-hidden /></Control>
        <span className="flex-1" />
        <Control label="Presenter notes (N)" pressed={notes} onClick={onNotes}><NotebookPen className="h-4 w-4" aria-hidden /></Control>
        <Control label="DNA" onClick={onDna}><Dna className="h-4 w-4" aria-hidden /></Control>
        <Control label="Full screen" onClick={fullScreen}><Maximize className="h-4 w-4" aria-hidden /></Control>
      </div>
      <button type="button" onClick={onAsk}
        className="fixed bottom-20 right-5 flex h-12 items-center gap-2 rounded-full bg-brand px-5 text-sm font-medium text-white shadow-card hover:bg-brand-hover">
        <MessageCircleQuestion className="h-5 w-5" aria-hidden /> Ask
      </button>
    </>
  );
}
