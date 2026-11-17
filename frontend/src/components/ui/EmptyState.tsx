import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface Props {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}

/** What a page or panel shows when it has nothing (yet), or cannot show anything. */
export function EmptyState({ title, description, action, icon, className }: Props) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-10 text-center', className)}>
      <div className="mb-3 text-ink-muted" aria-hidden>
        {icon ?? (
          <svg width="64" height="41" viewBox="0 0 64 41">
            <ellipse cx="32" cy="33" rx="32" ry="7" fill="#F5F5F5" />
            <path d="M55 13.5 44.9 2.1A2.6 2.6 0 0 0 43 1.3H21a2.6 2.6 0 0 0-1.9.8L9 13.5V23h46z" fill="none" stroke="#D9D9D9" />
            <path d="M9 13.5h12.2c1 0 1.8.9 1.8 2s.8 1.9 1.8 1.9h14.4c1 0 1.8-.9 1.8-1.9s.8-2 1.8-2H55V30a2 2 0 0 1-2 2H11a2 2 0 0 1-2-2z" fill="#FAFAFA" stroke="#D9D9D9" />
          </svg>
        )}
      </div>
      <h3 className="font-display text-base font-medium text-ink-strong">{title}</h3>
      {description && <div className="mt-1 max-w-md text-sm text-ink-muted">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
