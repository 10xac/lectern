import type { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { EmptyState } from './components/ui/EmptyState';
import { ToastProvider } from './components/ui/Toast';
import { AppShell, Page } from './layout/AppShell';
import { AuthProvider, useAuth } from './lib/auth';
import { AcceptInvitePage, inviteToken } from './pages/AcceptInvitePage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { ConsentPage } from './pages/ConsentPage';
import { DeckPage } from './pages/DeckPage';
import { DecksPage } from './pages/DecksPage';
import { LoginPage } from './pages/LoginPage';
import { ModelsPage } from './pages/ModelsPage';
import { OAuthAppsPage } from './pages/OAuthAppsPage';
import { PresentPage } from './pages/PresentPage';
import { RequireAdmin } from './pages/RequireAdmin';
import { TokensPage } from './pages/TokensPage';
import { UsersPage } from './pages/UsersPage';

/** Signed-in pages: with login on and nobody signed in, go to /login and come back afterwards. */
function RequireUser() {
  const { me } = useAuth();
  const location = useLocation();
  if (me.auth && !me.user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <Outlet />;
}

/** Old invite links are /#invite=<token>: send them to the invite page, keeping the token in the fragment. */
function LegacyInvite({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (location.pathname !== '/accept-invite' && inviteToken(location.hash)) return <Navigate to={`/accept-invite${location.hash}`} replace />;
  return <>{children}</>;
}

const admin = (page: ReactNode) => <RequireAdmin>{page}</RequireAdmin>;

// Page paths must not be API paths: the server answers /decks, /files, /me/… and /admin/settings itself.
export function AppRoutes() {
  return (
    <LegacyInvite>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/accept-invite" element={<AcceptInvitePage />} />
        <Route path="/connect/authorize" element={<ConsentPage />} />
        <Route path="/d/:deckId" element={<DeckPage shared />} />
        <Route path="/d/:deckId/present" element={<PresentPage shared />} />
        <Route element={<RequireUser />}>
          <Route path="/deck/:deckId/present" element={<PresentPage />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<DecksPage />} />
            <Route path="/deck/:deckId" element={<DeckPage />} />
            <Route path="/people/users" element={admin(<UsersPage />)} />
            <Route path="/connect/tokens" element={<TokensPage />} />
            <Route path="/connect/connections" element={<ConnectionsPage />} />
            <Route path="/connect/apps" element={admin(<OAuthAppsPage />)} />
            <Route path="/platform/models" element={admin(<ModelsPage />)} />
            <Route path="*" element={<Page><EmptyState title="Page not found" description="Check the address, or pick a page on the left." /></Page>} />
          </Route>
        </Route>
      </Routes>
    </LegacyInvite>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ToastProvider>
  );
}
