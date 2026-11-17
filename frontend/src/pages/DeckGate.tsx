import type { ReactNode } from 'react';
import { Link, Navigate, useLocation, useParams } from 'react-router-dom';
import { api, type Deck } from '../api';
import { EmptyState } from '../components/ui/EmptyState';
import { UnlockPrompt } from '../deck/UnlockPrompt';
import { useDeck } from '../hooks/useDeck';
import { useLoad } from '../lib/useLoad';

export type LoadedDeck = ReturnType<typeof useDeck> & { deck: Deck };

/** A visitor was refused a deck: ask for its password if it has one, else send them to sign in. */
function Refused({ deckId, retry }: { deckId: number; retry: () => void }) {
  const location = useLocation();
  const { data, error } = useLoad(api.listDecks);
  if (!data && !error) return <p className="p-8 text-center text-ink-muted" role="status">Loading…</p>;
  const listed = data?.find((d) => d.id === deckId);
  if (listed?.visibility === 'password') return <UnlockPrompt deckId={deckId} title={listed.title} onUnlocked={retry} />;
  return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
}

/** Load the deck in the URL, handling "not found" and "not allowed yet"; then render `children`. */
export function DeckGate({ children }: { children: (loaded: LoadedDeck) => ReactNode }) {
  const deckId = Number(useParams().deckId);
  const loaded = useDeck(deckId);
  const { deck, error, reload } = loaded;
  if (error?.status === 401) return <Refused deckId={deckId} retry={reload} />;
  if (error) {
    return (
      <EmptyState className="py-20" title={error.status === 404 ? 'Deck not found' : 'Could not open this deck'}
        description={error.message} action={<Link className="text-brand" to="/">All decks</Link>} />
    );
  }
  if (!deck) return <p className="p-8 text-center text-ink-muted" role="status">Loading deck…</p>;
  return <>{children({ ...loaded, deck })}</>;
}
