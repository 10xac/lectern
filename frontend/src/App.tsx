import { useEffect, useState } from 'react';
import { api, setCsrf, type Me, type User } from './api';
import { Account } from './components/Account';
import { DeckList } from './components/DeckList';
import { inviteToken, Login } from './components/Login';
import { DeckViewer } from './components/DeckViewer';
import { Upload } from './components/Upload';

/** Who is signed in. Login is required only when the server says so (``auth``). */
function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    void api.me().then((m) => {
      setCsrf(m.csrf);
      setMe(m);
    }, () => setMe({ auth: false, user: null, csrf: null }));
  }, []);
  const signIn = (user: User, csrf: string) => {
    setCsrf(csrf);
    setMe({ auth: true, user, csrf });
  };
  const signOut = () => void api.logout().then(() => setMe({ auth: true, user: null, csrf: null }));
  return { me, signIn, signOut };
}

/** Two screens: the deck list (with upload) and one open deck; plus sign-in and the account page. */
export default function App() {
  const [deckId, setDeckId] = useState<number | null>(null);
  const [version, setVersion] = useState(0);
  const [account, setAccount] = useState(false);
  const { me, signIn, signOut } = useMe();
  const invite = inviteToken(window.location.hash);

  if (!me) return null;
  if ((me.auth && !me.user) || invite) return <Login invite={invite} onIn={signIn} />;
  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" onClick={() => setDeckId(null)}>
          lectern
        </button>
        <span className="muted">every slide gets its own agent</span>
        <span className="spacer" />
        {me.user && <span className="muted">{me.user.email}</span>}
        <button type="button" aria-pressed={account} onClick={() => setAccount(!account)}>Account</button>
        {me.user && <button type="button" onClick={signOut}>Sign out</button>}
      </header>
      {account ? (
        <Account user={me.user} />
      ) : deckId === null ? (
        <div className="home">
          <Upload
            label="Upload a deck (.html, .pptx, Slides .json)"
            accept=".html,.htm,.pptx,.json"
            upload={api.uploadDeck}
            onDone={(deck) => {
              setVersion((v) => v + 1);
              setDeckId(deck.id);
            }}
          />
          <DeckList version={version} onOpen={setDeckId} />
        </div>
      ) : (
        <DeckViewer key={deckId} deckId={deckId} />
      )}
    </div>
  );
}
