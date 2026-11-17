import { X } from 'lucide-react';
import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../../lib/cn';
import { Button } from './Button';
import { useOverlay } from './useOverlay';

interface Base {
  title: ReactNode;
  /** The dialog's accessible name when `title` is not plain text. */
  label?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

function Header({ id, title, onClose }: { id: string; title: ReactNode; onClose: () => void }) {
  return (
    <header className="flex items-center gap-2 border-b border-line-soft px-6 py-4">
      <h2 id={id} className="mr-auto font-display text-base font-semibold text-ink-strong">{title}</h2>
      <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
        <X className="h-4 w-4" aria-hidden />
      </Button>
    </header>
  );
}

const SIZES = { nav: 'w-[250px]', sm: 'w-[360px]', md: 'w-[480px]', lg: 'w-[640px]' };

/** A panel that slides in from the side, over a dimmed page. */
export function Drawer({ title, label, onClose, children, footer, side = 'right', size = 'md' }: Base & {
  side?: 'left' | 'right';
  size?: keyof typeof SIZES;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();
  useOverlay(panel, onClose);
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/45" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        aria-labelledby={label ? undefined : id}
        tabIndex={-1}
        className={cn(
          'absolute inset-y-0 flex max-w-full flex-col bg-surface shadow-panel outline-none',
          side === 'right' ? 'right-0' : 'left-0',
          SIZES[size],
        )}
      >
        <Header id={id} title={title} onClose={onClose} />
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line-soft px-6 py-3">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}

/** A centred dialog; on phones it is a bottom sheet. */
export function Modal({ title, label, onClose, children, footer }: Base) {
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();
  useOverlay(panel, onClose);
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <div className="absolute inset-0 bg-black/45" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        aria-labelledby={label ? undefined : id}
        tabIndex={-1}
        className="relative flex max-h-[90vh] w-full flex-col rounded-t-lg bg-surface shadow-card outline-none sm:w-[520px] sm:rounded-lg"
      >
        <Header id={id} title={title} onClose={onClose} />
        <div className="overflow-y-auto px-6 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 px-6 pb-4 pt-2">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
