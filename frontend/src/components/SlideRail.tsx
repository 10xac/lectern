import type { Slide } from '../api';

interface Props {
  slides: Slide[];
  current: number;
  onSelect: (n: number) => void;
}

/** The list of slides on the left. */
export function SlideRail({ slides, current, onSelect }: Props) {
  return (
    <nav className="rail" aria-label="Slides">
      <ol>
        {slides.map((s) => (
          <li key={s.n}>
            <button
              type="button"
              aria-current={s.n === current ? 'true' : undefined}
              onClick={() => onSelect(s.n)}
            >
              <span className="rail-n">{s.n}</span> {s.title || `Slide ${s.n}`}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
