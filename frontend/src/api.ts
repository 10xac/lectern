// The backend's HTTP API, typed: the app's single client. In dev, Vite proxies /api to the server;
// in production the same server serves the app and maps /api/* itself.
import type {
  AccessToken, Attachment, ConsentView, Connection, Deck, DeckSummary, DnaGraph, Influence, InfluenceIn,
  Job, JobEvent, Me, ModelSettings, OAuthClient, Reconciled, Sharing, Slide, SlideChange, StoredFile, ThreadMessage, Trace,
  User, Visibility,
} from './types';

export type * from './types';

export const BASE = '/api';
const JOB_EVENTS = ['status', 'triage', 'researcher', 'budget', 'fuse', 'done'];

/** A failed request: the server's `detail` as the message, plus the HTTP status. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/** Follow a job's progress over SSE until its `done` event. Returns a function that stops following. */
function watchJob(id: string, onEvent: (event: JobEvent) => void): () => void {
  const source = new EventSource(`${BASE}/jobs/${id}/events`);
  for (const kind of JOB_EVENTS) {
    source.addEventListener(kind, (e) => {
      onEvent({ kind, data: JSON.parse((e as MessageEvent<string>).data) as Record<string, unknown> });
      if (kind === 'done') source.close();
    });
  }
  return () => source.close();
}

/** The session's CSRF token (from login or /auth/me); sent on every write. */
let csrf: string | null = null;
export const setCsrf = (token: string | null) => {
  csrf = token;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (csrf && init?.method && init.method !== 'GET') headers.set('X-CSRF-Token', csrf);
  const resp = await fetch(BASE + path, { ...init, headers });
  if (resp.status === 204) return undefined as T;
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const detail = typeof body.detail === 'string' ? body.detail : `${resp.status} ${resp.statusText}`;
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as T;
}

function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  return call<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  return call<T>(path, { method: 'POST', body: form });
}

const deckPath = (deckId: number, slide?: number | null) =>
  slide ? `/decks/${deckId}/slides/${slide}` : `/decks/${deckId}`;

export const api = {
  listDecks: () => call<DeckSummary[]>('/decks'),
  getDeck: (id: number) => call<Deck>(`/decks/${id}`),
  uploadDeck: (file: File) => upload<Deck>('/decks', file),
  uploadAttachment: (deckId: number, file: File) => upload<Attachment>(`/decks/${deckId}/attachments`, file),
  renameDeck: (deckId: number, title: string) => send<Deck>('PATCH', `/decks/${deckId}`, { title }),
  /** Delete a deck with its slides, DNA, chats and files. */
  deleteDeck: (deckId: number) => send<void>('DELETE', `/decks/${deckId}`),
  updateSlide: (deckId: number, n: number, change: SlideChange) => send<Slide>('PATCH', deckPath(deckId, n), change),
  /** Add a slide at 1-based position `at` (the end when omitted). */
  addSlide: (deckId: number, slide: SlideChange & { at?: number }) => send<Slide>('POST', `/decks/${deckId}/slides`, slide),
  /** Copy a slide; the copy lands right after it. */
  duplicateSlide: (deckId: number, n: number) => send<Slide>('POST', `${deckPath(deckId, n)}/duplicate`),
  moveSlide: (deckId: number, n: number, to: number) => send<Deck>('POST', `${deckPath(deckId, n)}/move`, { to }),
  deleteSlide: (deckId: number, n: number) => send<Deck>('DELETE', deckPath(deckId, n)),
  sharing: (deckId: number) => call<Sharing>(`/decks/${deckId}/sharing`),
  share: (deckId: number, visibility: Visibility, password?: string) =>
    send<Sharing>('PUT', `/decks/${deckId}/sharing`, { visibility, password: password || null }),
  unlock: (deckId: number, password: string) => send<{ unlocked: boolean }>('POST', `/decks/${deckId}/unlock`, { password }),
  /** Ask one slide (`slide` a number) or the whole deck (`slide` null): a 202 job. */
  ask: (deckId: number, slide: number | null, question: string) =>
    send<Job>('POST', `${deckPath(deckId, slide)}/ask`, { question }),
  messages: (deckId: number, slide: number | null) => call<ThreadMessage[]>(`${deckPath(deckId, slide)}/messages`),
  getJob: (id: string) => call<Job>(`/jobs/${id}`),
  feedback: (id: string, vote: 'up' | 'down') => send<Job>('POST', `/jobs/${id}/feedback`, { vote }),
  cancelJob: (id: string) => call<Job>(`/jobs/${id}`, { method: 'DELETE' }),
  watchJob,
  getTrace: (id: number) => call<Trace>(`/traces/${id}`),
  influences: (deckId: number, slide?: number) =>
    call<Influence[]>(`/decks/${deckId}/influences${slide ? `?slide=${slide}` : ''}`),
  addInfluence: (deckId: number, body: InfluenceIn) => send<Influence>('POST', `/decks/${deckId}/influences?via=ui`, body),
  updateInfluence: (deckId: number, id: string, body: Partial<InfluenceIn>) =>
    send<Influence>('PATCH', `/decks/${deckId}/influences/${id}`, body),
  removeInfluence: (deckId: number, id: string) => send<void>('DELETE', `/decks/${deckId}/influences/${id}`),
  uploadReference: (deckId: number, file: File) => upload<StoredFile>(`/decks/${deckId}/files`, file),
  deckFiles: (deckId: number) => call<StoredFile[]>(`/files?deck=${deckId}`),
  dnaGraph: (deckId: number, slide?: number) => call<DnaGraph>(`${deckPath(deckId, slide)}/dna`),
  dnaText: (deckId: number, slide?: number) => call<{ text: string }>(`${deckPath(deckId, slide)}/dna?format=text`),
  reconcile: () => send<Reconciled>('POST', '/files/reconcile'),
  relink: (fileId: string, path: string) => send<StoredFile>('POST', `/files/${fileId}/relink`, { path }),
  forget: (fileId: string) => send<void>('DELETE', `/files/${fileId}`),
  me: () => call<Me>('/auth/me'),
  login: (email: string, password: string) =>
    send<{ user: User; csrf: string }>('POST', '/auth/login', { email, password }),
  acceptInvite: (token: string, password: string) =>
    send<{ user: User; csrf: string }>('POST', '/auth/accept-invite', { token, password }),
  logout: () => send<void>('POST', '/auth/logout'),
  users: () => call<User[]>('/auth/users'),
  invite: (email: string, role: User['role']) =>
    send<{ user: User; invite_url: string }>('POST', '/auth/users', { email, role }),
  reinvite: (id: number) => send<{ user: User; invite_url: string }>('POST', `/auth/users/${id}/invite`),
  updateUser: (id: number, change: { role?: User['role']; status?: 'active' | 'disabled' }) =>
    send<User>('PATCH', `/auth/users/${id}`, change),
  tokens: () => call<AccessToken[]>('/me/tokens'),
  createToken: (name: string, days: number) =>
    send<{ token: AccessToken; secret: string }>('POST', '/me/tokens', { name, days }),
  revokeToken: (id: string) => send<void>('DELETE', `/me/tokens/${id}`),
  modelSettings: () => call<ModelSettings>('/admin/settings'),
  putSetting: (name: string, value: string | null) => send<ModelSettings>('PUT', `/admin/settings/${name}`, { value }),
  connections: () => call<Connection[]>('/me/connections'),
  endConnection: (id: string) => send<void>('DELETE', `/me/connections/${id}`),
  oauthClients: () => call<OAuthClient[]>('/admin/oauth/clients'),
  setClientDisabled: (id: string, disabled: boolean) =>
    send<{ status: string }>('POST', `/admin/oauth/clients/${id}/${disabled ? 'disable' : 'enable'}`),
  allConnections: () => call<Connection[]>('/admin/oauth/connections'),
  endAnyConnection: (id: string) => send<void>('DELETE', `/admin/oauth/connections/${id}`),
  consent: (txn: string) => call<ConsentView>(`/oauth/txn?txn=${encodeURIComponent(txn)}`),
  completeConsent: (txn: string, approve: boolean) =>
    send<{ redirect_to: string }>('POST', '/oauth/complete', { txn, approve }),
};
