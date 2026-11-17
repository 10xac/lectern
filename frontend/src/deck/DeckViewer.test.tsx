import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { applyEvent } from '../hooks/useSlideChat';
import { fakeDeckServer } from '../test/fakeDeckServer';
import { renderApp } from '../test/render';
import { stripMarkers } from './Citations';

vi.mock('../api', () => import('../test/apiMock'));

let server: ReturnType<typeof fakeDeckServer>;
beforeEach(() => {
  vi.clearAllMocks();
  server = fakeDeckServer();
});

async function open(path = '/deck/7') {
  renderApp(path);
  await screen.findByTitle('Slide 1');
}

async function ask(question: string) {
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: question } });
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Ask' })));
}

const chat = () => screen.getByRole('region', { name: /Chat with/ });
const rail = (n: number) => screen.getByRole('button', { name: new RegExp(`^Slide ${n}:`) });

describe('per-slide chat', () => {
  it('asks the current slide and shows the answer with chips, without markers', async () => {
    await open();
    await ask('What is this?');
    expect(api.ask).toHaveBeenCalledWith(7, 1, 'What is this?');
    expect(await within(chat()).findByText('Answer to "What is this?" on 1.')).toBeTruthy();
    expect(within(chat()).getByText('slide-1')).toBeTruthy();
    expect(within(chat()).getByRole('button', { name: 'slide 3 · notes' })).toBeTruthy();
    expect(within(chat()).getByLabelText('Confidence').textContent).toContain('fused 82%');
  });

  it('keeps a separate thread per slide', async () => {
    await open();
    await ask('first question');
    fireEvent.click(rail(2));
    expect(within(chat()).queryByText('first question')).toBeNull();
    await ask('second question');
    expect(api.ask).toHaveBeenLastCalledWith(7, 2, 'second question');
    fireEvent.click(rail(1));
    expect(await within(chat()).findByText('first question')).toBeTruthy();
    expect(within(chat()).queryByText('second question')).toBeNull();
  });

  it('posts the answer to the slide it was asked on, even after moving', async () => {
    server.state.hold = true;
    await open();
    await ask('slow one');
    const id = 'job|1|slow one';
    act(() => {
      server.watchers[id]({ kind: 'triage', data: { consult: ['K', 'M'], skip: {} } });
      server.watchers[id]({ kind: 'researcher', data: { source: 'K', state: 'running' } });
    });
    const lanes = screen.getByRole('list', { name: 'Running questions' });
    expect(within(lanes).getByText('deck · running')).toBeTruthy();
    expect(within(lanes).getByText('memory · queued')).toBeTruthy();
    fireEvent.click(rail(2));
    expect(screen.queryByRole('list', { name: 'Running questions' })).toBeNull();
    await act(async () => server.finish(id, 1, 'slow one'));
    expect(within(chat()).queryByText(/slow one/)).toBeNull();
    fireEvent.click(rail(1));
    expect(await within(chat()).findByText('Answer to "slow one" on 1.')).toBeTruthy();
    expect(screen.queryByRole('list', { name: 'Running questions' })).toBeNull();
  });

});

describe('answers', () => {
  it('jumps to the cited slide and highlights cited data', async () => {
    await open();
    await ask('Where are the risks?');
    fireEvent.click(await within(chat()).findByRole('button', { name: 'data 4 · part 2' }));
    expect(screen.getByText('data.csv').closest('li')?.dataset.highlight).toBe('true');
    fireEvent.click(within(chat()).getByRole('button', { name: 'slide 3 · notes' }));
    expect(rail(3).getAttribute('aria-current')).toBe('true');
    expect(screen.getAllByRole('heading', { name: 'Risks' }).length).toBeGreaterThan(0);
  });

  it('opens the trace drawer and votes', async () => {
    vi.mocked(api.feedback).mockResolvedValue({} as never);
    await open();
    await ask('trace me');
    fireEvent.click(await screen.findByRole('button', { name: 'Good answer' }));
    expect(api.feedback).toHaveBeenCalledWith('job|1|trace me', 'up');
    fireEvent.click(screen.getByRole('button', { name: 'trace' }));
    const drawer = await screen.findByRole('dialog', { name: 'Trace 11' });
    expect(await within(drawer).findByText('gate')).toBeTruthy();
    fireEvent.click(within(drawer).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('asks the whole deck from its own tab', async () => {
    await open();
    fireEvent.click(screen.getByRole('tab', { name: /Ask the deck/ }));
    await ask('Summarise');
    expect(api.ask).toHaveBeenCalledWith(7, null, 'Summarise');
    expect(await within(chat()).findByText('Answer to "Summarise" on deck.')).toBeTruthy();
  });

  it('shows a failed request in the thread', async () => {
    vi.mocked(api.ask).mockRejectedValueOnce(new Error('server down'));
    await open();
    await ask('hello?');
    expect(within(chat()).getByText('Something went wrong: server down')).toBeTruthy();
  });

  it('strips citation markers and folds job events', () => {
    expect(stripMarkers('One. [slide:2:body] Two [att:1:0].')).toBe('One. Two.');
    const job = { id: 'j', question: 'q', status: 'queued', lanes: {} };
    const triaged = applyEvent(job, { kind: 'triage', data: { consult: ['K'], skip: {} } });
    expect(applyEvent(triaged, { kind: 'status', data: { status: 'fusing' } })).toEqual({ ...job, status: 'fusing', lanes: { K: 'queued' } });
  });
});
