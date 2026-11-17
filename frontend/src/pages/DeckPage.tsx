import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { DeckViewer } from '../deck/DeckViewer';
import { Logo } from '../layout/Logo';
import { useAuth } from '../lib/auth';
import { buttonStyles } from '../components/ui/styles';
import { DeckGate } from './DeckGate';

/** A shared link's frame (no sider): the logo, and a way to sign in or open the deck in the app. */
function PublicFrame({ deckId, children }: { deckId: number; children: ReactNode }) {
  const { me } = useAuth();
  const signedIn = !me.auth || me.user;
  return (
    <div className="min-h-screen bg-surface-muted">
      <header className="sticky top-0 z-30 flex h-topbar items-center gap-3 border-b border-line-soft bg-surface px-4">
        <Link to={signedIn ? '/' : `/d/${deckId}`} aria-label="lectern" className="rounded"><Logo /></Link>
        <span className="flex-1" />
        {signedIn ? (
          <Link className={buttonStyles()} to={`/deck/${deckId}`}>Open in lectern</Link>
        ) : (
          <Link className={buttonStyles()} to={`/login?next=${encodeURIComponent(`/deck/${deckId}`)}`}>Sign in</Link>
        )}
      </header>
      <main>{children}</main>
    </div>
  );
}

/** The deck viewer, inside the app (`/deck/:id`) or from a shared link (`/d/:id`). */
export function DeckPage({ shared = false }: { shared?: boolean }) {
  const { me, canEdit, isAdmin } = useAuth();
  return (
    <DeckGate>
      {({ deck, editSlide, reload, setDeck }) => {
        const viewer = (
          <DeckViewer deck={deck} base={shared ? '/d' : '/deck'} canEdit={canEdit} admin={isAdmin} author={me.user?.email}
            editSlide={editSlide} reload={reload} onVisibility={(visibility) => setDeck({ ...deck, visibility })} />
        );
        return shared ? <PublicFrame deckId={deck.id}>{viewer}</PublicFrame> : viewer;
      }}
    </DeckGate>
  );
}
