import { MoreVertical, type LucideIcon } from 'lucide-react';
import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../../lib/cn';
import { Button } from './Button';

export interface MenuItem {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
}

interface Props {
  /** The trigger's accessible name, e.g. "Actions for Q3 review". */
  label: string;
  items: MenuItem[];
  /** Pass both to control the menu from outside (e.g. to open it on right-click). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
}

/**
 * A kebab button that opens a list of actions. Arrow keys, Home and End move between items;
 * Esc, Tab or a click elsewhere close it. The list is portalled with fixed positioning so a
 * scrolling container (the slide rail) cannot clip it.
 */
export function Menu({ label, items, open: controlled, onOpenChange, className }: Props) {
  const [own, setOwn] = useState(false);
  const open = controlled ?? own;
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const setOpen = (next: boolean) => {
    setOwn(next);
    onOpenChange?.(next);
  };
  const close = (refocus: boolean) => {
    setOpen(false);
    if (refocus) trigger.current?.focus();
  };
  return (
    <>
      <Button ref={trigger} variant="ghost" size="icon" aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
        className={className} onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(!open);
        }}>
        <MoreVertical className="h-4 w-4" aria-hidden />
      </Button>
      {open && <MenuList id={id} label={label} items={items} anchor={trigger} onClose={close} />}
    </>
  );
}

/** Below the trigger, right-aligned; above it when the trigger is near the bottom of the window. */
function usePosition(anchor: RefObject<HTMLElement | null>) {
  const [style, setStyle] = useState<CSSProperties>({});
  useLayoutEffect(() => {
    const r = anchor.current?.getBoundingClientRect();
    if (!r) return;
    const up = r.bottom > window.innerHeight - 260;
    setStyle({ left: r.right, transform: 'translateX(-100%)', ...(up ? { bottom: window.innerHeight - r.top + 4 } : { top: r.bottom + 4 }) });
  }, [anchor]);
  return style;
}

interface ListProps {
  id: string;
  label: string;
  items: MenuItem[];
  anchor: RefObject<HTMLButtonElement | null>;
  onClose: (refocus: boolean) => void;
}

function MenuList({ id, label, items, anchor, onClose }: ListProps) {
  const list = useRef<HTMLDivElement>(null);
  const style = usePosition(anchor);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(() => {
    list.current?.querySelector<HTMLElement>('[role="menuitem"]:not(:disabled)')?.focus();
    const outside = (e: Event) => {
      const t = e.target as Node;
      if (!list.current?.contains(t) && !anchor.current?.contains(t)) close.current(false);
    };
    document.addEventListener('mousedown', outside);
    document.addEventListener('contextmenu', outside);
    return () => {
      document.removeEventListener('mousedown', outside);
      document.removeEventListener('contextmenu', outside);
    };
  }, [anchor]);
  const onKey = (e: KeyboardEvent) => {
    const all = [...(list.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? [])];
    const at = all.indexOf(document.activeElement as HTMLElement);
    const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: all.length - 1 }[e.key];
    if (to !== undefined) {
      e.preventDefault();
      all[(to + all.length) % all.length]?.focus();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose(true);
    } else if (e.key === 'Tab') onClose(false);
    e.stopPropagation();
  };
  return createPortal(
    <div ref={list} id={id} role="menu" aria-label={label} onKeyDown={onKey} style={style}
      className="fixed z-50 min-w-[190px] rounded-md border border-line-soft bg-surface py-1 shadow-card">
      {items.map(({ label: name, icon: Icon, onSelect, danger, disabled }) => (
        <button key={name} type="button" role="menuitem" tabIndex={-1} disabled={disabled}
          className={cn('flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-surface-hover focus:bg-surface-hover focus:outline-none',
            'disabled:cursor-not-allowed disabled:opacity-50', danger ? 'text-danger-ink' : 'text-ink')}
          onClick={() => {
            onClose(true);
            onSelect();
          }}>
          {Icon && <Icon className="h-4 w-4" aria-hidden />}
          {name}
        </button>
      ))}
    </div>,
    document.body,
  );
}
