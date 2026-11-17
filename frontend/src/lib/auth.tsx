import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setCsrf, type Me, type User } from '../api';

interface Auth {
  me: Me;
  signIn: (user: User, csrf: string) => void;
  signOut: () => Promise<void>;
  /** Signed in, or login is off (one local user): may edit decks. */
  canEdit: boolean;
  /** An admin, or login is off. */
  isAdmin: boolean;
}

const AuthContext = createContext<Auth | null>(null);

/** Who is signed in. Login is required only when the server says so (`auth`). */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    void api.me().then(
      (m) => {
        setCsrf(m.csrf);
        setMe(m);
      },
      () => setMe({ auth: false, user: null, csrf: null }),
    );
  }, []);
  const signIn = useCallback((user: User, csrf: string) => {
    setCsrf(csrf);
    setMe({ auth: true, user, csrf });
  }, []);
  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setCsrf(null);
    setMe({ auth: true, user: null, csrf: null });
  }, []);
  const value = useMemo(() => {
    if (!me) return null;
    const canEdit = !me.auth || me.user !== null;
    return { me, signIn, signOut, canEdit, isAdmin: !me.auth || me.user?.role === 'admin' };
  }, [me, signIn, signOut]);
  if (!value) return <p className="p-8 text-center text-ink-muted" role="status">Loading…</p>;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('useAuth needs an AuthProvider');
  return auth;
}
