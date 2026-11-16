import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { DECK } from '../test/deck';
import { DeckViewer } from './DeckViewer';

vi.mock('../api', () => ({
  api: {
    getDeck: vi.fn(), ask: vi.fn(), getTrace: vi.fn(), uploadAttachment: vi.fn(), messages: vi.fn(async () => []),
  },
}));

beforeEach(() => {
  vi.mocked(api.getDeck).mockResolvedValue(DECK);
});

describe('DeckViewer', () => {
  it('shows the deck, the rail and the first slide in a sandboxed iframe', async () => {
    render(<DeckViewer deckId={7} />);
    expect(await screen.findByRole('heading', { name: 'Test deck' })).toBeTruthy();
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(3);
    const frame = screen.getByTitle('Slide 1');
    expect(frame.getAttribute('sandbox')).toBe('allow-scripts');
    expect(frame.getAttribute('srcdoc')).toContain('<h1>Intro</h1>');
  });

  it('switches slides from the rail and shows text cards', async () => {
    render(<DeckViewer deckId={7} />);
    fireEvent.click(await screen.findByRole('button', { name: /2 Plan/ }));
    expect(screen.getByRole('heading', { name: 'Plan' })).toBeTruthy();
    expect(screen.getByText('Step two')).toBeTruthy();
    expect(screen.getByText('No presenter notes.')).toBeTruthy();
    expect(screen.getByRole('button', { name: /2 Plan/ }).getAttribute('aria-current')).toBe('true');
  });

  it('toggles presenter notes', async () => {
    render(<DeckViewer deckId={7} />);
    const toggle = await screen.findByRole('button', { name: 'Show notes' });
    expect(screen.queryByText('Say hi')).toBeNull();
    fireEvent.click(toggle);
    expect(screen.getByText('Say hi')).toBeTruthy();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
  });

  it('moves with the arrow keys, within the deck', async () => {
    render(<DeckViewer deckId={7} />);
    await screen.findByTitle('Slide 1');
    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(screen.getByTitle('Slide 1')).toBeTruthy();
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByRole('heading', { name: 'Risks' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Show notes' }));
    expect(screen.getByText('Bring umbrellas')).toBeTruthy();
  });

  it('shows a load error', async () => {
    vi.mocked(api.getDeck).mockRejectedValueOnce(new Error('no deck 7'));
    render(<DeckViewer deckId={7} />);
    expect(await screen.findByText('no deck 7')).toBeTruthy();
  });
});
