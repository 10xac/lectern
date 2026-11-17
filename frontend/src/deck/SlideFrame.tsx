import { useEffect, useRef, useState } from 'react';
import type { Slide } from '../api';
import { cn } from '../lib/cn';

/** Slides are laid out at 960×540 and scaled to fit, so a thumbnail looks like the slide on stage. */
const W = 960;
const H = 540;

// In pick mode the slide marks what can be picked and reports the element clicked. It can only post a
// message, never read this page: the frame is sandboxed without allow-same-origin.
const PICK =
  '<style>[data-lectern-id]{outline:2px dashed #4F46E5;outline-offset:2px;cursor:crosshair}</style>' +
  "<script>document.addEventListener('click',function(e){var el=e.target.closest('[data-lectern-id]');" +
  "if(el){e.preventDefault();parent.postMessage({lecternPick:el.getAttribute('data-lectern-id')},'*');}},true);</script>";

/** Where a slide goes in its deck's shell document. */
const MARKER = '<!--lectern-slide-->';

/** The slide's document: inside the deck's shell (its head, fonts, scripts, wrappers) when it has one. */
export function slideDoc(html: string, shell?: string | null, picking = false) {
  // A function replacer, so `$&` or `$1` in the slide's html stay literal.
  const doc = shell?.includes(MARKER) ? shell.replace(MARKER, () => html) : html;
  return picking ? doc + PICK : doc;
}

function useScale() {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const node = box.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const watch = new ResizeObserver(([entry]) => setScale(entry.contentRect.width / W || 1));
    watch.observe(node);
    return () => watch.disconnect();
  }, []);
  return { box, scale };
}

interface Props {
  slide: Slide;
  /** The deck's shell document (Deck.shell), if any. */
  shell?: string | null;
  picking?: boolean;
  /** A rail thumbnail: not focusable, hidden from screen readers. */
  thumb?: boolean;
  className?: string;
}

/**
 * One slide at 16:9. HTML slides render in a sandboxed iframe: scripts may run, but without
 * allow-same-origin they cannot reach this page, its cookies or the API. Other slides are text cards.
 */
export function SlideFrame({ slide, shell, picking = false, thumb = false, className }: Props) {
  const { box, scale } = useScale();
  const name = thumb ? `Slide ${slide.n} thumbnail` : `Slide ${slide.n}`;
  return (
    <div ref={box} className={cn('relative aspect-video w-full overflow-hidden bg-white', className)} aria-hidden={thumb || undefined}>
      <div className={cn('absolute left-0 top-0 origin-top-left', thumb && 'pointer-events-none')} style={{ width: W, height: H, transform: `scale(${scale})` }}>
        {slide.html ? (
          <iframe
            className="h-full w-full border-0 bg-white"
            title={name}
            sandbox="allow-scripts"
            tabIndex={thumb ? -1 : undefined}
            srcDoc={slideDoc(slide.html, shell, picking)}
          />
        ) : (
          <div className="flex h-full w-full flex-col justify-center gap-4 bg-gradient-to-br from-white to-brand-soft/60 px-20" title={name}>
            <h2 className="font-display text-5xl font-semibold text-ink-strong">{slide.title || `Slide ${slide.n}`}</h2>
            {slide.body.split('\n').filter(Boolean).slice(0, 8).map((line, i) => (
              <p key={i} className="text-2xl leading-snug text-ink-soft">{line}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
