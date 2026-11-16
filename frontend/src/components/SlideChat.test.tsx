import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type JobEvent, type ThreadMessage } from '../api';
import { applyEvent } from '../hooks/useSlideChat';
import { answerFor, DECK } from '../test/deck';
import { DeckViewer } from './DeckViewer';
import { stripMarkers } from './SlideChat';

vi.mock('../api', () => ({
  api: {
    getDeck: vi.fn(), ask: vi.fn(), messages: vi.fn(), watchJob: vi.fn(), getTrace: vi.fn(),
    uploadAttachment: vi.fn(),
  },
}));

/** A tiny fake server: one thread per slide; a job answers when its watcher gets `done`. */
let threads: Record<number, ThreadMessage[]>;
let watchers: Record<string, (e: JobEvent) => void>;
let autoFinish: boolean;

function finish(jobId: string, slide: number, question: string) {
  const answer = answerFor(slide, question);
  threads[slide].push({ id: 0, deck_id: 7, slide, role: 'agent', text: answer.answer, job_id: jobId, answer });
  watchers[jobId]({ kind: 'done', data: { status: 'answered' } });
}

beforeEach(() => {
  threads = { 1: [], 2: [], 3: [] };
  watchers = {};
  autoFinish = true;
  vi.mocked(api.getDeck).mockResolvedValue(DECK);
  vi.mocked(api.messages).mockImplementation(async (_d, n) => [...threads[n]]);
  vi.mocked(api.ask).mockImplementation(async (_d, slide, question) => {
    const id = `job-${slide}-${question}`;
    threads[slide].push({ id: 0, deck_id: 7, slide, role: 'user', text: question, job_id: id, answer: null });
    return { id, deck_id: 7, slide, question, status: 'queued', answer: null, sources: [], notes: [], error: null };
  });
  vi.mocked(api.watchJob).mockImplementation((id, onEvent) => {
    watchers[id] = onEvent;
    const [, slide, question] = id.split('-');
    if (autoFinish) finish(id, Number(slide), question);
    return () => undefined;
  });
  vi.mocked(api.getTrace).mockResolvedValue({
    id: 11, deck_id: 7, template: 'answer', agent: 'slide-1', outcome: 'done',
    steps: [{ index: 0, node: 'gate', outcome: 'continue', block_ids: [], ms: 0.2 }],
  });
});

async function ask(question: string) {
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: question } });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
  });
}

const chat = () => screen.getByRole('region', { name: /Chat with slide/ });

describe('SlideChat', () => {
  it('asks the current slide and shows the answer with chips, without markers', async () => {
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('What is this?');
    expect(api.ask).toHaveBeenCalledWith(7, 1, 'What is this?');
    expect(await within(chat()).findByText('Answer to "What is this?" on 1.')).toBeTruthy();
    expect(within(chat()).getByText('slide-1')).toBeTruthy();
    expect(within(chat()).getByRole('button', { name: 'slide 3 · notes' })).toBeTruthy();
    expect(within(chat()).getByRole('button', { name: 'data 4 · part 2' })).toBeTruthy();
  });

  it('keeps a separate chat per slide', async () => {
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('first question');
    fireEvent.click(screen.getByRole('button', { name: /2 Plan/ }));
    expect(within(chat()).queryByText('first question')).toBeNull();
    await ask('second question');
    expect(api.ask).toHaveBeenLastCalledWith(7, 2, 'second question');
    fireEvent.click(screen.getByRole('button', { name: /1 Intro/ }));
    expect(within(chat()).getByText('first question')).toBeTruthy();
    expect(within(chat()).queryByText('second question')).toBeNull();
    await ask('follow up');
    expect(api.ask).toHaveBeenLastCalledWith(7, 1, 'follow up');
    expect(await within(chat()).findByText('follow up')).toBeTruthy();
  });

  it('jumps to the cited slide and highlights cited data', async () => {
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('Where are the risks?');
    fireEvent.click(within(chat()).getByRole('button', { name: 'data 4 · part 2' }));
    expect(screen.getByText('data.csv').closest('li')?.className).toBe('highlight');
    fireEvent.click(within(chat()).getByRole('button', { name: 'slide 3 · notes' }));
    expect(screen.getByRole('heading', { name: 'Risks' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /3 Risks/ }).getAttribute('aria-current')).toBe('true');
  });

  it('opens the trace drawer', async () => {
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('trace me');
    fireEvent.click(screen.getByRole('button', { name: 'trace' }));
    const drawer = await screen.findByRole('dialog', { name: 'Trace 11' });
    expect(await within(drawer).findByText('gate')).toBeTruthy();
    fireEvent.click(within(drawer).getByRole('button', { name: 'Close trace' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows a failed request in the chat', async () => {
    vi.mocked(api.ask).mockRejectedValueOnce(new Error('server down'));
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('hello?');
    expect(within(chat()).getByText('Something went wrong: server down')).toBeTruthy();
  });

  it('strips citation markers from answer text', () => {
    expect(stripMarkers('One. [slide:2:body] Two [att:1:0].')).toBe('One. Two.');
  });
});

describe('job lanes', () => {
  it('shows running jobs as lanes and posts the answer to the slide it was asked on', async () => {
    autoFinish = false;
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    await ask('slow one');
    const id = 'job-1-slow one';
    act(() => {
      watchers[id]({ kind: 'triage', data: { consult: ['K', 'M'], skip: {} } });
      watchers[id]({ kind: 'researcher', data: { source: 'K', state: 'running' } });
    });
    const lanes = screen.getByRole('list', { name: 'Running questions' });
    expect(within(lanes).getByText('deck · running')).toBeTruthy();
    expect(within(lanes).getByText('memory · queued')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /2 Plan/ }));
    expect(screen.queryByRole('list', { name: 'Running questions' })).toBeNull();
    await act(async () => finish(id, 1, 'slow one'));
    expect(within(chat()).queryByText(/slow one/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /1 Intro/ }));
    expect(await within(chat()).findByText('Answer to "slow one" on 1.')).toBeTruthy();
    expect(screen.queryByRole('list', { name: 'Running questions' })).toBeNull();
  });

  it('folds events into a live job', () => {
    const job = { id: 'j', question: 'q', status: 'queued', lanes: {} };
    const triaged = applyEvent(job, { kind: 'triage', data: { consult: ['K'], skip: {} } });
    expect(applyEvent(triaged, { kind: 'status', data: { status: 'fusing' } })).toEqual({
      ...job, status: 'fusing', lanes: { K: 'queued' },
    });
    expect(applyEvent(job, { kind: 'budget', data: {} })).toBe(job);
  });
});
