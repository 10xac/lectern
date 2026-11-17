// The shapes of lectern's HTTP API (re-exported by api.ts).

export type SourceKind = 'html' | 'pptx' | 'gslides';

export interface Slide {
  n: number;
  title: string;
  body: string;
  notes: string;
  html: string | null;
  persona: string | null;
  file_id?: string | null;
}

export interface Attachment {
  id: number;
  deck_id: number;
  name: string;
  chunks: number;
}

export type Visibility = 'private' | 'public' | 'password';

export interface DeckSummary {
  id: number;
  title: string;
  source: SourceKind;
  visibility?: Visibility;
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

/** One SSE event of a job: `status`, `triage`, `researcher`, `budget`, `fuse` or `done`. */
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

export interface Sharing {
  visibility: Visibility;
  has_password: boolean;
}

/** An app (such as claude.ai) a person connected to lectern over OAuth. */
export interface Connection {
  id: string;
  user_id: number;
  email: string;
  client: string;
  created_at: number;
  last_used_at: number | null;
}

export interface OAuthClient {
  id: string;
  name: string;
  redirect_uris: string[];
  created_at: number;
  last_used_at: number | null;
  disabled: boolean;
}

/** What the OAuth consent page shows. */
export interface ConsentView {
  client: string;
  redirect_host: string | null;
  scopes: string[];
}
