import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Drawer } from '../components/ui/Overlay';
import { cn } from '../lib/cn';
import { AccountMenu } from './AccountMenu';
import { Logo } from './Logo';
import { SideNav } from './SideNav';

/** The signed-in frame: a 64px top bar, a collapsible sider (a drawer under 800px) and the page. */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 flex h-topbar shrink-0 items-center gap-3 border-b border-line-soft bg-surface px-4">
        <Button variant="ghost" size="icon" className="nav:hidden" aria-label="Open navigation" onClick={() => setDrawer(true)}>
          <Menu className="h-5 w-5" aria-hidden />
        </Button>
        <Link to="/" aria-label="lectern home" className="rounded">
          <Logo />
        </Link>
        <span className="hidden text-sm text-ink-muted lg:inline">every slide gets its own agent</span>
        <span className="flex-1" />
        <AccountMenu />
      </header>
      <div className="flex flex-1">
        <aside
          className={cn(
            'sticky top-topbar hidden h-[calc(100vh-64px)] shrink-0 flex-col border-r border-line-soft bg-surface nav:flex',
            collapsed ? 'w-sider-collapsed' : 'w-sider',
          )}
        >
          <div className="flex-1 overflow-y-auto">
            <SideNav collapsed={collapsed} />
          </div>
          <Button
            variant="ghost"
            className="m-2 justify-center"
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" aria-hidden /> : <PanelLeftClose className="h-4 w-4" aria-hidden />}
          </Button>
        </aside>
        <main id="main" className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
      {drawer && (
        <Drawer title={<Logo />} label="Navigation" side="left" size="nav" onClose={() => setDrawer(false)}>
          <div className="-mx-6">
            <SideNav onGo={() => setDrawer(false)} />
          </div>
        </Drawer>
      )}
    </div>
  );
}

/** A normal page inside the shell: padded, at most 1600px wide. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-content px-4 py-6 md:px-6 lg:px-8">{children}</div>;
}
