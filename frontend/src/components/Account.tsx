import { useEffect, useState, type FormEvent } from 'react';
import { api, type AccessToken, type ModelSettings, type User } from '../api';

const day = (t: number | null) => (t ? new Date(t * 1000).toISOString().slice(0, 10) : '—');

/** Personal access tokens for MCP: each is shown once, then only its name and dates. */
export function TokensPanel() {
  const [tokens, setTokens] = useState<AccessToken[]>([]);
  const [name, setName] = useState('');
  const [days, setDays] = useState(30);
  const [secret, setSecret] = useState<string | null>(null);
  const load = () => void api.tokens().then(setTokens, () => setTokens([]));
  useEffect(load, []);
  const create = async (e: FormEvent) => {
    e.preventDefault();
    setSecret((await api.createToken(name, days)).secret);
    setName('');
    load();
  };
  const mcpUrl = `${window.location.origin}/mcp/`;
  return (
    <section aria-label="MCP tokens">
      <h2>MCP tokens</h2>
      <form onSubmit={create}>
        <input aria-label="Token name" placeholder="e.g. Claude Code on my laptop" required value={name} onChange={(e) => setName(e.target.value)} />
        <input aria-label="Days" type="number" min={1} max={90} value={days} onChange={(e) => setDays(Number(e.target.value))} />
        <button type="submit">Create token</button>
      </form>
      {secret && (
        <div className="secret" role="status">
          <p>Copy it now: it is not shown again.</p>
          <code>{secret}</code>
          <p className="muted">claude mcp add --transport http lectern {mcpUrl} --header "Authorization: Bearer {secret}"</p>
        </div>
      )}
      <ul>
        {tokens.map((t) => (
          <li key={t.id}>
            {t.name} · expires {day(t.expires_at)} · last used {day(t.last_used_at)}{' '}
            {t.revoked_at ? <span className="muted">revoked</span> : <button type="button" onClick={() => void api.revokeToken(t.id).then(load)}>Revoke</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Admins invite people (a one-time link to send them), change roles, and disable or re-invite. */
export function UsersPanel() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<User['role']>('member');
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => void api.users().then(setUsers, () => setUsers([]));
  useEffect(load, []);
  const act = (p: Promise<{ invite_url?: string } | unknown>) =>
    void p.then((out) => {
      setError(null);
      const url = (out as { invite_url?: string } | undefined)?.invite_url;
      if (url) setLink(url);
      load();
    }, (e: Error) => setError(e.message));
  const invite = (e: FormEvent) => {
    e.preventDefault();
    act(api.invite(email, role));
    setEmail('');
  };
  return (
    <section aria-label="Users">
      <h2>Users</h2>
      <form onSubmit={invite}>
        <input aria-label="Invite email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as User['role'])}>
          <option>member</option>
          <option>admin</option>
        </select>
        <button type="submit">Invite</button>
      </form>
      {link && <p role="status">Send this one-time link (valid 7 days): <code>{link}</code></p>}
      {error && <p className="error">{error}</p>}
      <ul>
        {users.map((u) => (
          <li key={u.id}>
            {u.email} · {u.role} · {u.status}{' '}
            <button type="button" onClick={() => act(api.updateUser(u.id, { role: u.role === 'admin' ? 'member' : 'admin' }))}>
              {u.role === 'admin' ? 'Make member' : 'Make admin'}
            </button>
            {u.status !== 'invited' && (
              <button type="button" onClick={() => act(api.updateUser(u.id, { status: u.status === 'disabled' ? 'active' : 'disabled' }))}>
                {u.status === 'disabled' ? 'Enable' : 'Disable'}
              </button>
            )}
            <button type="button" onClick={() => act(api.reinvite(u.id))}>New link</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Admins choose the model, System1 and the API keys; keys are write-only (set/unset, last 4). */
export function SettingsPanel() {
  const [data, setData] = useState<ModelSettings | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => void api.modelSettings().then(setData, (e: Error) => setError(e.message)), []);
  const save = (name: string, value: string | null) =>
    void api.putSetting(name, value).then((d) => {
      setData(d);
      setDraft({ ...draft, [name]: '' });
      setError(null);
    }, (e: Error) => setError(e.message));
  if (!data) return error ? <p className="error">{error}</p> : null;
  return (
    <section aria-label="Models and keys">
      <h2>Models and keys</h2>
      <p className="muted">Triage (System1): {data.system1.kind}{data.system1.model ? ` · ${data.system1.model}` : ''} — {data.system1.why}</p>
      {data.settings.map((s) => (
        <label key={s.name} className="setting">
          {s.name} <span className="muted">({s.source})</span>
          <input aria-label={s.name} defaultValue={s.value} onBlur={(e) => e.target.value !== s.value && save(s.name, e.target.value || null)} />
        </label>
      ))}
      {data.keys.map((k) => (
        <label key={k.name} className="setting">
          {k.name} <span className="muted">{k.set ? `set …${k.last4 ?? ''} (${k.source})` : 'unset'}</span>
          <input aria-label={k.name} type="password" autoComplete="off" value={draft[k.name] ?? ''}
            disabled={!data.store_configured} onChange={(e) => setDraft({ ...draft, [k.name]: e.target.value })} />
          <button type="button" disabled={!draft[k.name]} onClick={() => save(k.name, draft[k.name])}>Save</button>
          {k.source === 'lectern' && <button type="button" onClick={() => save(k.name, null)}>Remove</button>}
        </label>
      ))}
      {!data.store_configured && <p className="muted">Set LECTERN_SECRET_KEY on the server to store keys here.</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

/** The account page: everyone's tokens; admins also see users and the model settings. */
export function Account({ user }: { user: User | null }) {
  const isAdmin = !user || user.role === 'admin'; // no user: login is off, the one local user
  return (
    <div className="account">
      {user && <TokensPanel />}
      {isAdmin && user && <UsersPanel />}
      {isAdmin && <SettingsPanel />}
    </div>
  );
}
