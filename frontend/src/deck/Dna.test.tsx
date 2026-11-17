import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type DnaGraph, type Influence } from '../api';
import { fakeDeckServer } from '../test/fakeDeckServer';
import { renderApp } from '../test/render';
import { layout } from './DnaGraph';
import { elementsOf } from './InfluenceDrawer';

vi.mock('../api', () => import('../test/apiMock'));

const GRAPH: DnaGraph = {
  nodes: [
    { id: 'deck:7', type: 'deck', label: 'Test deck', layer: 0 },
    { id: 'inf:ab12', type: 'influence', label: 'Why umbrellas', layer: 1, degree: 'high' },
    { id: 'slide:1', type: 'slide', label: '1. Intro', layer: 2 },
  ],
  edges: [
    { from: 'deck:7', to: 'inf:ab12', type: 'contains' },
    { from: 'inf:ab12', to: 'slide:1', type: 'shapes', degree: 'high', weight: 1 },
  ],
};
const INFLUENCE: Influence = {
  id: 'ab12', deck_id: 7, via: 'ui', created_at: 1, updated_at: 1,
  scope: { kind: 'slide', slides: [1] }, target: { component: 'whole', element_id: null },
  kind: 'reasoning', degree: 'high', title: 'Why umbrellas', body: 'It rains.', refs: [], author: { type: 'human', name: 'ada' },
};

beforeEach(() => {
  vi.clearAllMocks();
  fakeDeckServer();
  vi.mocked(api.dnaGraph).mockResolvedValue(GRAPH);
  vi.mocked(api.dnaText).mockResolvedValue({ text: '(high) Why umbrellas [dna:ab12]' });
  vi.mocked(api.influences).mockResolvedValue([INFLUENCE]);
  vi.mocked(api.addInfluence).mockResolvedValue(INFLUENCE);
  vi.mocked(api.updateInfluence).mockResolvedValue(INFLUENCE);
});

const click = async (el: HTMLElement) => act(async () => fireEvent.click(el));

async function openDna() {
  renderApp('/deck/7');
  await click(await screen.findByRole('tab', { name: /DNA/ }));
  return screen.findByRole('group', { name: 'DNA graph' });
}

describe('DNA panel', () => {
  it('draws the graph and switches to the whole deck and to text', async () => {
    const graph = await openDna();
    expect(within(graph).getAllByTestId('dna-node')).toHaveLength(3);
    expect(within(graph).getAllByTestId('dna-edge')).toHaveLength(2);
    expect(api.dnaGraph).toHaveBeenLastCalledWith(7, 1);
    await click(screen.getByRole('radio', { name: 'Whole deck' }));
    expect(api.dnaGraph).toHaveBeenLastCalledWith(7, undefined);
    await click(screen.getByRole('radio', { name: 'Text' }));
    expect(screen.getByLabelText('DNA text').textContent).toContain('(high) Why umbrellas');
  });

  it('opens an influence from the graph (keyboard too) and from the text', async () => {
    const graph = await openDna();
    await act(async () => fireEvent.keyDown(within(graph).getByRole('button', { name: 'Open influence Why umbrellas' }), { key: 'Enter' }));
    const drawer = await screen.findByRole('dialog', { name: 'Edit influence' });
    expect((within(drawer).getByLabelText('Title') as HTMLInputElement).value).toBe('Why umbrellas');
    await click(within(drawer).getByRole('button', { name: 'Save' }));
    expect(api.updateInfluence).toHaveBeenCalledWith(7, 'ab12', expect.objectContaining({ title: 'Why umbrellas', degree: 'high' }));
    await click(screen.getByRole('radio', { name: 'Text' }));
    await click(screen.getByRole('button', { name: 'open' }));
    expect(await screen.findByRole('dialog', { name: 'Edit influence' })).toBeTruthy();
  });

  it('lays nodes out in rows by layer', () => {
    const at = layout(GRAPH);
    expect(at['deck:7'].y).toBeLessThan(at['inf:ab12'].y);
    expect(at['inf:ab12'].y).toBeLessThan(at['slide:1'].y);
  });
});

describe('influence drawer', () => {
  it('adds an influence to the current slide with a link reference', async () => {
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Influence' }));
    const drawer = screen.getByRole('dialog', { name: 'New influence' });
    fireEvent.click(within(drawer).getByLabelText('idea'));
    fireEvent.change(within(drawer).getByLabelText('Title'), { target: { value: 'Start warm' } });
    fireEvent.change(within(drawer).getByLabelText('Reference URL'), { target: { value: 'https://example.org/x' } });
    fireEvent.click(within(drawer).getByRole('button', { name: 'Add link' }));
    await click(within(drawer).getByRole('button', { name: 'Save' }));
    expect(api.addInfluence).toHaveBeenCalledWith(7, expect.objectContaining({
      scope: { kind: 'slide', slides: [1] }, kind: 'idea', degree: 'medium', title: 'Start warm',
      refs: [{ type: 'url', url: 'https://example.org/x' }], author: { type: 'human', name: 'ada@example.org' },
    }));
  });

  it('scopes a new influence to the selected slides', async () => {
    renderApp('/deck/7');
    fireEvent.click(await screen.findByLabelText('Select slide 2'));
    fireEvent.click(screen.getByLabelText('Select slide 3'));
    await click(screen.getByRole('button', { name: 'Add influence to selected' }));
    const drawer = screen.getByRole('dialog', { name: 'New influence' });
    fireEvent.change(within(drawer).getByLabelText('Title'), { target: { value: 'Shared idea' } });
    await click(within(drawer).getByRole('button', { name: 'Save' }));
    expect(api.addInfluence).toHaveBeenCalledWith(7, expect.objectContaining({ scope: { kind: 'slides', slides: [2, 3] } }));
  });

  it('picks an element on the slide, accepting only valid ids while picking', async () => {
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Influence' }));
    fireEvent.change(screen.getByLabelText('Component'), { target: { value: 'text' } });
    await click(screen.getByRole('button', { name: 'Pick on slide' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect((screen.getByTitle('Slide 1') as HTMLIFrameElement).srcdoc).toContain('lecternPick');
    await act(async () => window.dispatchEvent(new MessageEvent('message', { data: { lecternPick: 'bad id<script>' } })));
    expect(screen.queryByRole('dialog')).toBeNull();
    await act(async () => window.dispatchEvent(new MessageEvent('message', { data: { lecternPick: 's1.title' } })));
    const drawer = await screen.findByRole('dialog', { name: 'New influence' });
    expect((within(drawer).getByLabelText('Element') as HTMLSelectElement).value).toBe('s1.title');
    expect((within(drawer).getByLabelText('Component') as HTMLSelectElement).value).toBe('element');
  });

  it('finds the targetable elements in slide markup', () => {
    expect(elementsOf('<h1 class="t" data-lectern-id="s1.title">x</h1><img data-lectern-id="fig-1">')).toEqual([
      { tag: 'h1', id: 's1.title' }, { tag: 'img', id: 'fig-1' },
    ]);
  });
});
