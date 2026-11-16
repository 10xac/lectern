import type { Slide } from '../api';
import { NotesToggle } from './NotesToggle';

/**
 * One slide. HTML slides render in a sandboxed iframe: scripts may run, but without
 * allow-same-origin they cannot reach this page, its cookies or the API. Other slides are text cards.
 */
// In pick mode the slide reports the element clicked; it can only post a message, never read this page.
const PICK =
  "<script>document.addEventListener('click',function(e){var el=e.target.closest('[data-lectern-id]');" +
  "if(el){e.preventDefault();parent.postMessage({lecternPick:el.getAttribute('data-lectern-id')},'*');}},true);</script>";

export function SlidePane({ slide, picking = false }: { slide: Slide; picking?: boolean }) {
  return (
    <article className={`slide-pane${picking ? ' picking' : ''}`} aria-label={`Slide ${slide.n}`}>
      {slide.html ? (
        <iframe className="slide-frame" title={`Slide ${slide.n}`} sandbox="allow-scripts" srcDoc={picking ? slide.html + PICK : slide.html} />
      ) : (
        <div className="slide-card">
          <h2>{slide.title || `Slide ${slide.n}`}</h2>
          {slide.body.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      )}
      <NotesToggle notes={slide.notes} />
    </article>
  );
}
