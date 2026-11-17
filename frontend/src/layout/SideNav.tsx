import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { cn } from '../lib/cn';
import { navFor, type NavItem } from './nav';

function Item({ item, collapsed, onGo }: { item: NavItem; collapsed: boolean; onGo?: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onGo}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          'relative flex h-10 items-center gap-3 rounded-r px-6 text-sm text-ink hover:bg-surface-hover',
          collapsed && 'justify-center px-0',
          isActive && 'bg-surface-selected font-medium text-ink-strong before:absolute before:inset-y-0 before:left-0 before:w-[5px] before:bg-brand',
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className={cn(collapsed && 'sr-only')}>{item.label}</span>
    </NavLink>
  );
}

/** The sider's navigation: foldable groups of links; icons only when collapsed. */
export function SideNav({ collapsed = false, onGo }: { collapsed?: boolean; onGo?: () => void }) {
  const { isAdmin } = useAuth();
  const [folded, setFolded] = useState<Record<string, boolean>>({});
  return (
    <nav aria-label="Main" className="py-3">
      {navFor(isAdmin).map((g) => (
        <div key={g.label} className="mb-2">
          {!collapsed && (
            <button
              type="button"
              aria-expanded={!folded[g.label]}
              onClick={() => setFolded((f) => ({ ...f, [g.label]: !f[g.label] }))}
              className="flex w-full items-center justify-between px-6 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint hover:text-ink"
            >
              {g.label}
              <ChevronDown className={cn('h-3 w-3 transition-transform', folded[g.label] && '-rotate-90')} aria-hidden />
            </button>
          )}
          {(collapsed || !folded[g.label]) && (
            <ul>
              {g.items.map((i) => (
                <li key={i.to}><Item item={i} collapsed={collapsed} onGo={onGo} /></li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </nav>
  );
}
