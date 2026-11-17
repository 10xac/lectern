import { vi } from 'vitest';
import { api, type JobEvent, type ThreadMessage } from '../api';
import { answerFor, DECK } from './deck';

/**
 * A tiny fake server for deck tests: one thread per slide (key 0 is the deck's own thread); a job
 * answers when its watcher gets `done` (at once, unless `hold` is set).
 */
export function fakeDeckServer() {
  const threads: Record<number, ThreadMessage[]> = { 0: [], 1: [], 2: [], 3: [] };
  const watchers: Record<string, (e: JobEvent) => void> = {};
  const state = { hold: false };
  const finish = (jobId: string, slide: number | null, question: string) => {
    const answer = answerFor(slide, question);
    threads[slide ?? 0].push({ id: 0, deck_id: 7, slide, role: 'agent', text: answer.answer, job_id: jobId, answer });
    watchers[jobId]({ kind: 'done', data: { status: 'answered' } });
  };
  vi.mocked(api.getDeck).mockResolvedValue(structuredClone(DECK));
  vi.mocked(api.messages).mockImplementation(async (_d, n) => [...threads[n ?? 0]]);
  vi.mocked(api.ask).mockImplementation(async (_d, slide, question) => {
    const id = `job|${slide ?? 'deck'}|${question}`;
    threads[slide ?? 0].push({ id: 0, deck_id: 7, slide, role: 'user', text: question, job_id: id, answer: null });
    return { id, deck_id: 7, slide, question, status: 'queued', answer: null, sources: [], notes: [], error: null };
  });
  vi.mocked(api.watchJob).mockImplementation((id, onEvent) => {
    watchers[id] = onEvent;
    const [, slide, question] = id.split('|');
    if (!state.hold) finish(id, slide === 'deck' ? null : Number(slide), question);
    return () => undefined;
  });
  vi.mocked(api.getTrace).mockResolvedValue({
    id: 11, deck_id: 7, template: 'answer', agent: 'slide-1', outcome: 'done',
    steps: [{ index: 0, node: 'gate', outcome: 'continue', block_ids: [], ms: 0.2 }],
  });
  vi.mocked(api.dnaGraph).mockResolvedValue({ nodes: [], edges: [] });
  vi.mocked(api.dnaText).mockResolvedValue({ text: '' });
  vi.mocked(api.deckFiles).mockResolvedValue([]);
  return { threads, watchers, state, finish };
}
