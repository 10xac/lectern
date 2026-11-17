import { Search } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { EmptyState } from './EmptyState';
import { inputStyles } from './styles';

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | null;
  rowKey: (row: T) => string | number;
  label: string;
  empty?: ReactNode;
  /** With `search`, a box above the table keeps rows whose text matches. */
  search?: (row: T) => string;
}

/** A plain, accessible table: header row, loading and empty states, an optional search box. */
export function DataTable<T>({ columns, rows, rowKey, label, empty, search }: Props<T>) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const shown = rows && search && q ? rows.filter((r) => search(r).toLowerCase().includes(q)) : rows;
  return (
    <div>
      {search && (
        <label className="relative mb-3 block max-w-xs">
          <span className="sr-only">Search {label}</span>
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <input className={cn(inputStyles(), 'pl-8')} placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
      )}
      <div className="overflow-x-auto rounded-lg border border-line-soft">
        <table className="w-full min-w-[560px] border-collapse text-left text-sm" aria-label={label} aria-busy={rows === null}>
          <thead className="bg-surface-muted text-ink-strong">
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={cn('border-b border-line-soft px-4 py-3 font-medium', c.className)}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown?.map((row) => (
              <tr key={rowKey(row)} className="border-b border-line-soft bg-surface last:border-0 hover:bg-surface-muted">
                {columns.map((c) => (
                  <td key={c.key} className={cn('px-4 py-3 align-middle', c.className)}>{c.cell(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows === null && <p className="bg-surface px-4 py-8 text-center text-ink-muted">Loading…</p>}
        {shown?.length === 0 && <div className="bg-surface">{empty ?? <EmptyState title={q ? 'No matches' : 'Nothing here yet'} />}</div>}
      </div>
    </div>
  );
}
