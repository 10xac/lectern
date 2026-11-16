import { useCallback, useEffect, useState } from 'react';
import { api, type Citation, type Confidence, type JobEvent, type ThreadMessage } from '../api';

export interface Message {
  role: 'user' | 'agent';
  text: string;
  agent?: string;
  citations?: Citation[];
  traceId?: number | null;
  failed?: boolean;
  jobId?: string | null;
  confidence?: Confidence | null;
}

/** A job still running on a slide: its status and one lane per researcher (source → state). */
export interface LiveJob {
  id: string;
  question: string;
  status: string;
  lanes: Record<string, string>;
}

/** Every slide has its own thread: threads are keyed by deck id and slide number. */
export const chatKey = (deckId: number, slide: number) => `${deckId}:${slide}`;

const toMessage = (m: ThreadMessage): Message =>
  m.answer
    ? {
        role: 'agent', text: m.text, agent: m.answer.agent, citations: m.answer.citations,
        traceId: m.answer.trace_id, jobId: m.job_id, confidence: m.answer.confidence,
      }
    : { role: m.role, text: m.text };

/** Fold one SSE event into a live job. */
export function applyEvent(job: LiveJob, event: JobEvent): LiveJob {
  if (event.kind === 'status' || event.kind === 'done') return { ...job, status: String(event.data.status) };
  if (event.kind === 'researcher') {
    return { ...job, lanes: { ...job.lanes, [String(event.data.source)]: String(event.data.state) } };
  }
  if (event.kind === 'triage') {
    const lanes = Object.fromEntries((event.data.consult as string[]).map((s) => [s, 'queued']));
    return { ...job, lanes: { ...lanes, ...job.lanes } };
  }
  return job;
}

/**
 * The thread for one slide, kept on the server. Asking starts a background job; its progress
 * streams in as lanes, and when it is done the thread of the slide it was asked on is reloaded,
 * even if the user has moved to another slide meanwhile. Several jobs may run at once.
 */
export function useSlideChat(deckId: number, slide: number) {
  const [threads, setThreads] = useState<Record<string, Message[]>>({});
  const [live, setLive] = useState<Record<string, LiveJob[]>>({});
  const key = chatKey(deckId, slide);

  const reload = useCallback(async (d: number, n: number) => {
    const k = chatKey(d, n);
    try {
      const rows = await api.messages(d, n);
      setThreads((prev) => ({ ...prev, [k]: rows.map(toMessage) }));
    } catch (e) {
      const failed: Message = { role: 'agent', text: `Something went wrong: ${(e as Error).message}`, failed: true };
      setThreads((prev) => ({ ...prev, [k]: [...(prev[k] ?? []), failed] }));
    }
  }, []);

  useEffect(() => {
    if (threads[key] === undefined) void reload(deckId, slide);
  }, [deckId, key, reload, slide, threads]);

  const send = useCallback(
    async (question: string) => {
      const k = key;
      setThreads((prev) => ({ ...prev, [k]: [...(prev[k] ?? []), { role: 'user', text: question }] }));
      try {
        const job = await api.ask(deckId, slide, question);
        const update = (fn: (j: LiveJob) => LiveJob | null) =>
          setLive((prev) => ({
            ...prev,
            [k]: (prev[k] ?? []).flatMap((j) => (j.id === job.id ? (fn(j) ?? []) : [j])),
          }));
        setLive((prev) => ({ ...prev, [k]: [...(prev[k] ?? []), { id: job.id, question, status: job.status, lanes: {} }] }));
        api.watchJob(job.id, (event) => {
          update((j) => (event.kind === 'done' ? null : applyEvent(j, event)));
          if (event.kind === 'done') void reload(deckId, slide);
        });
      } catch (e) {
        const failed: Message = { role: 'agent', text: `Something went wrong: ${(e as Error).message}`, failed: true };
        setThreads((prev) => ({ ...prev, [k]: [...(prev[k] ?? []), failed] }));
      }
    },
    [deckId, key, reload, slide],
  );

  return { messages: threads[key] ?? [], jobs: live[key] ?? [], send };
}
