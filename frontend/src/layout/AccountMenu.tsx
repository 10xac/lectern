import { LogOut } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { initials } from '../lib/format';
import { StatusBadge } from '../components/ui/StatusBadge';

/** A round initials avatar that opens a small account menu. */
export function AccountMenu() {
  const { me, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', away);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);
  const user = me.user;
  const out = async () => {
    await signOut();
    navigate('/login');
  };
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label="Account"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-9 shrink-0 items-center [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11 justify-center rounded-full bg-brand-soft font-display text-sm font-semibold text-brand-strong hover:ring-2 hover:ring-brand/30"
      >
        {user ? initials(user.email) : 'L'}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-11 z-40 w-64 rounded-lg bg-surface p-2 shadow-card">
          <div className="border-b border-line-soft px-3 pb-3 pt-1">
            <p className="truncate font-medium text-ink-strong">{user?.email ?? 'Local user'}</p>
            <p className="mt-1 flex gap-1">
              <StatusBadge tone={user?.role === 'admin' || !user ? 'brand' : 'neutral'}>{user?.role ?? 'admin'}</StatusBadge>
              {!me.auth && <StatusBadge tone="warning">login off</StatusBadge>}
            </p>
          </div>
          {user && (
            <button type="button" role="menuitem" onClick={() => void out()} className="mt-1 flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm hover:bg-surface-hover">
              <LogOut className="h-4 w-4" aria-hidden /> Sign out
            </button>
          )}
          {!user && <p className="px-3 py-2 text-xs text-ink-muted">Login is off: this server has one local user.</p>}
        </div>
      )}
    </div>
  );
}
