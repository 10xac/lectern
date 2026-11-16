// The backend's HTTP API, typed. In dev, Vite proxies /api to the FastAPI server.

export type SourceKind = 'html' | 'pptx' | 'gslides';

export interface Slide {
  n: number;
  title: string;
  body: string;
  notes: string;
  html: string | null;
  persona: string | null;
}

export interface Attachment {
  id: number;
  deck_id: number;
  name: string;
  chunks: number;
}

export interface DeckSummary {
  id: number;
  title: string;
  source: SourceKind;
}

export interface Deck extends DeckSummary {
  outline: string;
  slides: Slide[];
  attachments: Attachment[];
}

export interface Citation {
  block_id: string;
  slide: number | null;
  attachment: number | null;
  influence?: string | null;
  file?: string | null;
}

export type Degree = 'high' | 'medium' | 'low' | 'general';
export type InfluenceKind = 'idea' | 'reasoning' | 'explanation' | 'note' | 'citation' | 'reference';
export type ComponentKind = 'whole' | 'text' | 'image' | 'chart' | 'layout' | 'concept' | 'element';

export interface Ref {
  type: 'url' | 'file';
  url?: string | null;
  file_id?: string | null;
  label?: string | null;
}

/** One DNA record: what shaped a slide, some slides or the whole deck, and how strongly. */
export interface InfluenceIn {
  scope: { kind: 'slide' | 'slides' | 'deck'; slides: number[] };
  target: { component: ComponentKind; element_id?: string | null; label?: string | null };
  kind: InfluenceKind;
  degree: Degree;
  title: string;
  body: string;
  refs: Ref[];
  author: { type: 'human' | 'ai'; name: string; tool?: string | null; model?: string | null };
}

export interface Influence extends InfluenceIn {
  id: string;
  deck_id: number;
  via: string;
  created_at: number;
  updated_at: number;
}

export interface StoredFile {
  id: string;
  path: string;
  deck_id: number | null;
  role: string;
  mime: string;
  size: number;
  version: number;
  status: 'live' | 'missing';
}

export interface DnaNode {
  id: string;
  type: 'deck' | 'slide' | 'component' | 'influence' | 'file' | 'url';
  label: string;
  layer: number;
  degree?: Degree;
  stale?: boolean;
}

export interface DnaEdge {
  from: string;
  to: string;
  type: 'shapes' | 'derived' | 'cites' | 'contains';
  degree?: Degree;
  weight?: number;
}

export interface DnaGraph {
  nodes: DnaNode[];
  edges: DnaEdge[];
}

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'member';
  status: 'invited' | 'active' | 'disabled';
}

export interface Me {
  auth: boolean;
  user: User | null;
  csrf: string | null;
}

export interface AccessToken {
  id: string;
  name: string;
  created_at: number;
  expires_at: number;
  revoked_at: number | null;
  last_used_at: number | null;
}

export interface ModelSettings {
  settings: { name: string; value: string; source: string }[];
  keys: { name: string; set: boolean; source: string; last4: string | null }[];
  store_configured: boolean;
  system1: { kind: string; provider: string | null; model: string | null; key: string; why: string };
}

export interface Reconciled {
  missing: StoredFile[];
  unregistered: string[];
  suggestions: Record<string, string>;
}

/** How sure a job's answer is: per source, fused (Bayesian and Dempster-Shafer), and triage's view. */
export interface Confidence {
  verdict: 'answer' | 'qualify' | 'ask' | 'abstain';
  why: string;
  triage: { by: string; class: string; engage: number; hops: number; note: string };
  fusion: { best: string; p_best: number; z: number; kappa: number } | null;
  sources: { source: string; status: string; r: number; g: number; reason: string }[];
}

export interface Answer {
  answer: string;
  citations: Citation[];
  agent: string;
  trace_id: number | null;
  outcome: string;
  confidence?: Confidence | null;
}

export interface TraceStep {
  index: number;
  node: string;
  outcome: string;
  block_ids: string[];
  ms: number | null;
}

export interface Trace {
  id: number;
  deck_id: number | null;
  template: string;
  agent: string;
  outcome: string;
  steps: TraceStep[];
}

export type SourceName = 'P' | 'W' | 'K' | 'M';
export type JobStatus =
  | 'queued' | 'triaging' | 'researching' | 'fusing'
  | 'answered' | 'abstained' | 'asked' | 'failed' | 'cancelled';

export interface SourceReport {
  source: SourceName;
  status: 'done' | 'skipped' | 'failed' | 'timeout';
  reason: string;
  answer: string;
  r: number;
  g: number;
  block_ids: string[];
  tool_calls: number;
}

export interface Job {
  id: string;
  deck_id: number;
  slide: number | null;
  question: string;
  status: JobStatus;
  answer: Answer | null;
  sources: SourceReport[];
  notes: string[];
  error: string | null;
}

/** One SSE event of a job: `status`, `triage`, `researcher`, `budget` or `done`. */
export interface JobEvent {
  kind: string;
  data: Record<string, unknown>;
}

export interface ThreadMessage {
  id: number;
  deck_id: number;
  slide: number | null;
  role: 'user' | 'agent';
  text: string;
  job_id: string | null;
  answer: Answer | null;
}

const BASE = '/api';
const JOB_EVENTS = ['status', 'triage', 'researcher', 'budget', 'done'];

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
    throw new Error(typeof body.detail === 'string' ? body.detail : `${resp.status} ${resp.statusText}`);
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

export const api = {
  listDecks: () => call<DeckSummary[]>('/decks'),
  getDeck: (id: number) => call<Deck>(`/decks/${id}`),
  uploadDeck: (file: File) => upload<Deck>('/decks', file),
  uploadAttachment: (deckId: number, file: File) => upload<Attachment>(`/decks/${deckId}/attachments`, file),
  ask: (deckId: number, slide: number, question: string) =>
    call<Job>(`/decks/${deckId}/slides/${slide}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
  messages: (deckId: number, slide: number) => call<ThreadMessage[]>(`/decks/${deckId}/slides/${slide}/messages`),
  getJob: (id: string) => call<Job>(`/jobs/${id}`),
  feedback: (id: string, vote: 'up' | 'down') =>
    call<Job>(`/jobs/${id}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vote }),
    }),
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
  dnaGraph: (deckId: number, slide?: number) =>
    call<DnaGraph>(slide ? `/decks/${deckId}/slides/${slide}/dna` : `/decks/${deckId}/dna`),
  dnaText: (deckId: number, slide?: number) =>
    call<{ text: string }>(`${slide ? `/decks/${deckId}/slides/${slide}/dna` : `/decks/${deckId}/dna`}?format=text`),
  reconcile: () => send<Reconciled>('POST', '/files/reconcile'),
  relink: (fileId: string, path: string) => send<StoredFile>('POST', `/files/${fileId}/relink`, { path }),
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
  forget: (fileId: string) => send<void>('DELETE', `/files/${fileId}`),
};
