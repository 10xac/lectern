import { ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface Crumb {
  label: string;
  to?: string;
}

interface Props {
  title: ReactNode;
  crumbs?: Crumb[];
  actions?: ReactNode;
  description?: ReactNode;
}

/** A page's breadcrumbs, title, description and main actions. */
export function PageHeader({ title, crumbs, actions, description }: Props) {
  return (
    <div className="mb-6">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2">
          <ol className="flex flex-wrap items-center gap-1 text-sm text-ink-faint">
            {crumbs.map((c, i) => (
              <li key={c.label} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
                {c.to ? <Link className="hover:text-ink" to={c.to}>{c.label}</Link> : <span className="text-ink-soft">{c.label}</span>}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto font-display text-xl font-semibold text-ink-strong md:text-2xl">{title}</h1>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {description && <div className="mt-1 max-w-3xl text-sm text-ink-soft">{description}</div>}
    </div>
  );
}
