import { render } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { vi } from 'vitest';
import { api, type Me } from '../api';
import { AppRoutes } from '../App';
import { ToastProvider } from '../components/ui/Toast';
import { AuthProvider } from '../lib/auth';

export const ADMIN: Me = { auth: true, user: { id: 1, email: 'ada@example.org', role: 'admin', status: 'active' }, csrf: 'c' };
export const MEMBER: Me = { auth: true, user: { id: 2, email: 'bob@example.org', role: 'member', status: 'active' }, csrf: 'c' };
export const VISITOR: Me = { auth: true, user: null, csrf: null };
export const LOCAL: Me = { auth: false, user: null, csrf: null };

/** Shows the router's current location, so tests can check redirects. */
function Where() {
  const l = useLocation();
  return <output data-testid="where">{l.pathname + l.search + l.hash}</output>;
}

/** Render the whole app at `path`, as `me`. The api module must be mocked by the test file. */
export function renderApp(path: string, me: Me = ADMIN) {
  vi.mocked(api.me).mockResolvedValue(me);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
          <Where />
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}
