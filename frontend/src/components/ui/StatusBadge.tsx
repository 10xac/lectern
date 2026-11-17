import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { badgeStyles, type Tone } from './styles';

/** A small coloured tag. */
export function StatusBadge({ tone, children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span className={cn(badgeStyles({ tone }), className)} title={title}>
      {children}
    </span>
  );
}
