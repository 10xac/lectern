import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface Props {
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
  /** The card's accessible name when its title is not plain text. */
  label?: string;
}

/** A white panel with an optional title row. */
export function Card({ title, actions, className, bodyClassName, children, label }: Props) {
  return (
    <section
      aria-label={label ?? (typeof title === 'string' ? title : undefined)}
      className={cn('rounded-lg border border-line-soft bg-surface', className)}
    >
      {(title || actions) && (
        <header className="flex min-h-14 flex-wrap items-center gap-2 border-b border-line-soft px-6 py-3">
          {title && <h2 className="mr-auto font-display text-lg font-medium text-ink-strong">{title}</h2>}
          {actions}
        </header>
      )}
      <div className={cn('p-6', bodyClassName)}>{children}</div>
    </section>
  );
}
