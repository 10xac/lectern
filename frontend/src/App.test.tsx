import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { api } from './api';
import App from './App';
import { DECK } from './test/deck';

vi.mock('./api', () => ({
  api: {
    listDecks: vi.fn(), getDeck: vi.fn(), uploadDeck: vi.fn(), ask: vi.fn(), getTrace: vi.fn(),
    messages: vi.fn(async () => []),
    me: vi.fn(async () => ({ auth: false, user: null, csrf: null })),
  },
  setCsrf: vi.fn(),
}));

describe('App', () => {
  it('lists decks, opens one and goes back', async () => {
    vi.mocked(api.listDecks).mockResolvedValue([{ id: 7, title: 'Test deck', source: 'html' }]);
    vi.mocked(api.getDeck).mockResolvedValue(DECK);
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Test deck' }));
    expect(await screen.findByTitle('Slide 1')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'lectern' }));
    expect(await screen.findByText('HTML artifact', { exact: false })).toBeTruthy();
  });

  it('uploads a deck and opens it', async () => {
    vi.mocked(api.listDecks).mockResolvedValue([]);
    vi.mocked(api.getDeck).mockResolvedValue(DECK);
    vi.mocked(api.uploadDeck).mockResolvedValue(DECK);
    render(<App />);
    expect(await screen.findByText(/No decks yet/)).toBeTruthy();
    const input = screen.getByLabelText(/Upload a deck/) as HTMLInputElement;
    const file = new File(['<section></section>'], 'talk.html', { type: 'text/html' });
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    expect(api.uploadDeck).toHaveBeenCalledWith(file);
    expect(await screen.findByTitle('Slide 1')).toBeTruthy();
  });

  it('shows an upload error', async () => {
    vi.mocked(api.listDecks).mockResolvedValue([]);
    vi.mocked(api.uploadDeck).mockRejectedValue(new Error('unknown deck format'));
    render(<App />);
    const input = await screen.findByLabelText(/Upload a deck/);
    await act(async () => {
      fireEvent.change(input, { target: { files: [new File(['x'], 'x.bin')] } });
    });
    expect(screen.getByText('unknown deck format')).toBeTruthy();
  });
});
