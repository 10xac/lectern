import { useEffect, useRef, type RefObject } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])';
/** Open overlays, innermost last: only the top one answers Esc and Tab. */
const stack: object[] = [];

/**
 * Behaviour every modal overlay shares: focus moves in (and back out on close), Tab stays inside,
 * Esc closes the top overlay, and the page behind does not scroll.
 */
export function useOverlay(panel: RefObject<HTMLElement | null>, onClose: () => void) {
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const me = {};
    stack.push(me);
    const before = document.activeElement as HTMLElement | null;
    const node = panel.current;
    const first = node?.querySelector<HTMLElement>('[autofocus], [data-autofocus]') ?? node;
    first?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me || !node) return;
      if (e.key === 'Escape') {
        e.stopPropagation();
        close.current();
      } else if (e.key === 'Tab') trapTab(e, node);
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      stack.splice(stack.indexOf(me), 1);
      document.removeEventListener('keydown', onKey, true);
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, [panel]);
}

function trapTab(e: KeyboardEvent, node: HTMLElement) {
  const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)];
  if (items.length === 0) return e.preventDefault();
  const [first, last] = [items[0], items[items.length - 1]];
  const active = document.activeElement;
  if (e.shiftKey && (active === first || active === node)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && active === last) {
    e.preventDefault();
    first.focus();
  }
}
