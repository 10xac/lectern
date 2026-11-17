import type { MouseEvent } from 'react';
import type { Slide } from '../api';
import { cn } from '../lib/cn';
import { SlideFrame } from './SlideFrame';

interface Props {
  slides: Slide[];
  current: number;
  onSelect: (n: number) => void;
  selected: number[];
  /** Toggle one slide in the selection; with `range`, select from the last one to this one. */
  onToggle: (n: number, range: boolean) => void;
  selectable: boolean;
}

/** The slides on the left: thumbnails to open one, checkboxes (or shift-click) to select several. */
export function SlideRail({ slides, current, onSelect, selected, onToggle, selectable }: Props) {
  const open = (e: MouseEvent, n: number) => {
    if (selectable && (e.shiftKey || e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onToggle(n, e.shiftKey);
    } else onSelect(n);
  };
  return (
    <nav aria-label="Slides" className="min-h-0">
      <ol className="flex gap-3 overflow-x-auto p-3 lg:flex-col lg:overflow-x-visible">
        {slides.map((s) => {
          const active = s.n === current;
          const chosen = selected.includes(s.n);
          return (
            <li key={s.n} className="relative w-40 shrink-0 lg:w-auto">
              {selectable && (
                <input type="checkbox" aria-label={`Select slide ${s.n}`} checked={chosen} onChange={() => undefined} onClick={(e) => onToggle(s.n, e.shiftKey)}
                  className="absolute right-2 top-2 z-10 h-4 w-4 cursor-pointer accent-[rgb(var(--brand))]" />
              )}
              <button type="button" aria-label={`Slide ${s.n}: ${s.title || 'untitled'}`} aria-current={active ? 'true' : undefined} onClick={(e) => open(e, s.n)}
                className={cn('block w-full rounded-md p-1.5 text-left transition-colors hover:bg-surface-hover', active && 'bg-surface-selected', chosen && 'ring-2 ring-brand/40')}>
                <SlideFrame slide={s} thumb className={cn('rounded border', active ? 'border-brand' : 'border-line-soft')} />
                <span className="mt-1.5 flex items-baseline gap-1.5 text-xs">
                  <span className={cn('font-semibold', active ? 'text-brand' : 'text-ink-muted')}>{s.n}</span>
                  <span className="truncate text-ink">{s.title || `Slide ${s.n}`}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
