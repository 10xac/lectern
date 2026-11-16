import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type DnaGraph as Graph } from '../api';
import { useDna } from '../hooks/useDna';
import { DnaGraph, layout } from './DnaGraph';
import { DnaPanel, FilesCheck } from './DnaPanel';
import { elementsOf, InfluenceDrawer } from './InfluenceDrawer';

vi.mock('../api', () => ({
  api: {
    addInfluence: vi.fn(async () => ({})), updateInfluence: vi.fn(async () => ({})), influences: vi.fn(async () => []),
    deckFiles: vi.fn(async () => [{ id: 'f1', path: 'refs/7/memo.pdf', role: 'reference' }]),
    uploadReference: vi.fn(), dnaGraph: vi.fn(), dnaText: vi.fn(), reconcile: vi.fn(), relink: vi.fn(async () => ({})),
    forget: vi.fn(async () => undefined),
  },
}));

const GRAPH: Graph = {
  nodes: [
    { id: 'deck', type: 'deck', label: 'Deck', layer: 0 },
    { id: 'inf:a', type: 'influence', label: 'Board memo', layer: 1, degree: 'high' },
    { id: 'inf:b', type: 'influence', label: 'House style', layer: 1, degree: 'general', stale: true },
    { id: 'slide:1', type: 'slide', label: '1. Revenue', layer: 3 },
  ],
  edges: [
    { from: 'deck', to: 'slide:1', type: 'contains' },
    { from: 'inf:a', to: 'slide:1', type: 'shapes', degree: 'high', weight: 1 },
    { from: 'inf:b', to: 'deck', type: 'shapes', degree: 'general', weight: 0.2 },
  ],
};

beforeEach(() => vi.clearAllMocks());

function drawer(picked: string | null = null) {
  const onPick = vi.fn();
  const onSaved = vi.fn();
  const html = '<section><h1 data-lectern-id="h1-1">T</h1><img data-lectern-id="img-1"></section>';
  const ui = render(
    <InfluenceDrawer deckId={7} slides={[{ n: 1 }, { n: 2 }, { n: 3 }]} current={2} elements={elementsOf(html)}
      picked={picked} onPick={onPick} onClose={() => undefined} onSaved={onSaved} />,
  );
  return { ...ui, onPick, onSaved };
}

describe('InfluenceDrawer', () => {
  it('sends the scope, the picked slides, the degree and the references', async () => {
    const { onSaved } = drawer();
    fireEvent.click(screen.getByLabelText('choose slides'));
    fireEvent.click(screen.getByLabelText('Slide 3'));
    fireEvent.click(screen.getByLabelText('high'));
    fireEvent.change(screen.getByLabelText('Kind'), { target: { value: 'idea' } });
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Board memo' } });
    fireEvent.change(screen.getByLabelText('Reference URL'), { target: { value: 'https://example.org' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add link' }));
    fireEvent.change(await screen.findByLabelText('Existing file'), { target: { value: 'f1' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Save' })));
    expect(api.addInfluence).toHaveBeenCalledWith(7, expect.objectContaining({
      scope: { kind: 'slides', slides: [2, 3] }, degree: 'high', kind: 'idea', title: 'Board memo',
      refs: [{ type: 'url', url: 'https://example.org' }, { type: 'file', file_id: 'f1' }],
    }));
    expect(onSaved).toHaveBeenCalled();
  });

  it('targets an element: from the list, or picked on the slide', async () => {
    const { onPick, rerender } = drawer();
    fireEvent.click(screen.getByLabelText('whole deck'));
    fireEvent.change(screen.getByLabelText('Component'), { target: { value: 'image' } });
    fireEvent.click(screen.getByRole('button', { name: 'Pick on slide' }));
    expect(onPick).toHaveBeenCalled();
    expect(within(screen.getByLabelText('Element')).getAllByRole('option').map((o) => o.textContent)).toEqual(['(none)', 'h1-1', 'img-1']);
    rerender(
      <InfluenceDrawer deckId={7} slides={[{ n: 1 }]} current={2} elements={[{ id: 'img-1' }]} picked="img-1"
        onPick={onPick} onClose={() => undefined} onSaved={() => undefined} />,
    );
    expect((screen.getByLabelText('Element') as HTMLSelectElement).value).toBe('img-1');
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'x' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Save' })));
    expect(api.addInfluence).toHaveBeenCalledWith(7, expect.objectContaining({
      scope: { kind: 'deck', slides: [] }, target: { component: 'element', element_id: 'img-1' },
    }));
  });
});

describe('DNA views', () => {
  it('draws one node per graph node and edges as thick as their degree', () => {
    const onOpen = vi.fn();
    render(<DnaGraph graph={GRAPH} onOpen={onOpen} />);
    expect(screen.getAllByTestId('dna-node')).toHaveLength(4);
    const widths = screen.getAllByTestId('dna-edge').map((e) => e.getAttribute('stroke-width'));
    expect(widths).toEqual(['1', '5', '1.8']);
    expect(screen.getByText('House style ⚠')).toBeTruthy();
    fireEvent.click(screen.getByText('Board memo'));
    expect(onOpen).toHaveBeenCalledWith('a');
    expect(layout(GRAPH)['slide:1'].y).toBeGreaterThan(layout(GRAPH)['inf:a'].y);
  });

  it('shows the text trace with links to each record', async () => {
    vi.mocked(api.dnaGraph).mockResolvedValue(GRAPH);
    vi.mocked(api.dnaText).mockResolvedValue({ text: 'Slide 1 was shaped by:\n- (high) Board memo [dna:a]' });
    const onOpen = vi.fn();
    render(<DnaPanel deckId={7} slide={1} version={0} onOpen={onOpen} />);
    expect(await screen.findByRole('img', { name: 'DNA graph' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Text' }));
    expect(screen.getByText(/\(high\) Board memo/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'open' }));
    expect(onOpen).toHaveBeenCalledWith('a');
    fireEvent.click(screen.getByLabelText('whole deck'));
    await waitFor(() => expect(api.dnaText).toHaveBeenLastCalledWith(7, undefined));
  });

  it('relinks a missing file or deletes its metadata', async () => {
    vi.mocked(api.reconcile).mockResolvedValue({
      missing: [{ id: 'f9', path: 'refs/old.pdf', deck_id: 7, role: 'reference', mime: 'application/pdf', size: 1, version: 1, status: 'missing' }],
      unregistered: ['refs/new.pdf'], suggestions: { f9: 'refs/new.pdf' },
    });
    render(<FilesCheck />);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Check files' })));
    expect((screen.getByLabelText('New file for refs/old.pdf') as HTMLSelectElement).value).toBe('refs/new.pdf');
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Relink' })));
    expect(api.relink).toHaveBeenCalledWith('f9', 'refs/new.pdf');
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Delete metadata' })));
    expect(api.forget).toHaveBeenCalledWith('f9');
  });
});

function Probe() {
  const dna = useDna(7);
  return (
    <div>
      <button type="button" onClick={dna.pick}>pick</button>
      <span>{dna.picking ? 'picking' : 'idle'}:{dna.picked ?? '-'}</span>
    </div>
  );
}

describe('useDna', () => {
  it('takes one element id from the slide while picking, and nothing else', () => {
    render(<Probe />);
    act(() => window.dispatchEvent(new MessageEvent('message', { data: { lecternPick: 'img-1' } })));
    expect(screen.getByText('idle:-')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'pick' }));
    act(() => window.dispatchEvent(new MessageEvent('message', { data: { lecternPick: '<script>' } })));
    expect(screen.getByText('picking:-')).toBeTruthy();
    act(() => window.dispatchEvent(new MessageEvent('message', { data: { lecternPick: 'img-1' } })));
    expect(screen.getByText('idle:img-1')).toBeTruthy();
  });
});
