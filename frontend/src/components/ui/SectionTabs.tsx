import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

export interface Tab<K extends string> {
  key: K;
  label: ReactNode;
}

interface Props<K extends string> {
  tabs: Tab<K>[];
  value: K;
  onChange: (key: K) => void;
  label: string;
  className?: string;
}

/** A row of tabs (ARIA tablist; ←/→ move between them). The panel is the caller's `TabPanel`. */
export function SectionTabs<K extends string>({ tabs, value, onChange, label, className }: Props<K>) {
  const base = useId();
  const row = useRef<HTMLDivElement>(null);
  const onKey = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.key === value);
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    e.stopPropagation();
    const next = tabs[(i + step + tabs.length) % tabs.length];
    onChange(next.key);
    row.current?.querySelector<HTMLElement>(`[data-key="${next.key}"]`)?.focus();
  };
  return (
    <div ref={row} role="tablist" aria-label={label} onKeyDown={onKey} className={cn('flex gap-6 border-b border-line-soft', className)}>
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          data-key={t.key}
          id={`${base}-${t.key}`}
          aria-selected={t.key === value}
          tabIndex={t.key === value ? 0 : -1}
          onClick={() => onChange(t.key)}
          className={cn(
            '-mb-px whitespace-nowrap border-b-2 py-2.5 text-sm transition-colors',
            t.key === value ? 'border-brand font-medium text-brand' : 'border-transparent text-ink-soft hover:text-brand-hover',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
