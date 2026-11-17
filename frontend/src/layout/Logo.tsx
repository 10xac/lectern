import { cn } from '../lib/cn';

/** lectern's mark: a lectern (a slanted reading desk on a stand) inside a rounded square. */
export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('h-8 w-8', className)} aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-brand" />
      <path d="M8 11.5 24 8.5v4.5L8 16z" fill="#fff" />
      <path d="M14.5 16.5h3V24h-3z" fill="#fff" opacity=".85" />
      <path d="M10.5 24.5h11" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/** The mark with the word "lectern". */
export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <Mark />
      {!compact && <span className="font-display text-lg font-semibold tracking-tight text-ink-strong">lectern</span>}
    </span>
  );
}
