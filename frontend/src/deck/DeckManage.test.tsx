import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type Deck } from '../api';
import { DECK } from '../test/deck';
import { fakeDeckServer } from '../test/fakeDeckServer';
import { renderApp, VISITOR } from '../test/render';
import { SlideFrame, slideDoc } from './SlideFrame';

vi.mock('../api', () => import('../test/apiMock'));

beforeEach(() => {
  vi.clearAllMocks();
  fakeDeckServer();
});

const click = async (el: HTMLElement) => act(async () => fireEvent.click(el));
const item = (name: string) => within(screen.getByRole('menu')).getByRole('menuitem', { name });
const renumber = (slides: Deck['slides']): Deck => ({ ...structuredClone(DECK), slides: slides.map((s, i) => ({ ...s, n: i + 1 })) });

describe('the deck list menu', () => {
  beforeEach(() => {
    vi.mocked(api.listDecks).mockResolvedValue([{ id: 7, title: 'Test deck', source: 'html', visibility: 'private' }, { id: 8, title: 'Other', source: 'pptx' }]);
  });

  it('deletes a deck after confirming and drops its card', async () => {
    vi.mocked(api.deleteDeck).mockResolvedValue(undefined);
    renderApp('/');
    await click(await screen.findByRole('button', { name: 'Actions for Test deck' }));
    expect(screen.getByRole('button', { name: 'Actions for Test deck' }).getAttribute('aria-expanded')).toBe('true');
    await click(item('Delete'));
    const dialog = screen.getByRole('dialog', { name: 'Delete Test deck?' });
    expect(dialog.textContent).toContain('slides, DNA, chats and files');
    expect(api.deleteDeck).not.toHaveBeenCalled();
    vi.mocked(api.listDecks).mockResolvedValue([{ id: 8, title: 'Other', source: 'pptx' }]);
    await click(within(dialog).getByRole('button', { name: 'Delete deck' }));
    expect(api.deleteDeck).toHaveBeenCalledWith(7);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(within(screen.getByRole('list', { name: 'Decks' })).queryByText('Test deck')).toBeNull();
    expect(screen.getByText('Other')).toBeTruthy();
  });

  it('renames a deck', async () => {
    vi.mocked(api.renameDeck).mockResolvedValue({ ...DECK, title: 'Q3 review' });
    renderApp('/');
    await click(await screen.findByRole('button', { name: 'Actions for Other' }));
    await click(item('Rename'));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Q3 review' } });
    await click(screen.getByRole('button', { name: 'Rename' }));
    expect(api.renameDeck).toHaveBeenCalledWith(8, 'Q3 review');
    expect(api.listDecks).toHaveBeenCalledTimes(2);
  });

  it('closes on Escape and returns focus to its button', async () => {
    renderApp('/');
    const trigger = await screen.findByRole('button', { name: 'Actions for Other' });
    await click(trigger);
    expect(document.activeElement).toBe(item('Rename'));
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(item('Delete'));
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});

describe('the slide rail menu', () => {
  it('moves a slide down from the right-click menu and follows it', async () => {
    const [a, b, c] = DECK.slides;
    vi.mocked(api.moveSlide).mockResolvedValue(renumber([b, a, c]));
    renderApp('/deck/7');
    fireEvent.contextMenu(await screen.findByRole('button', { name: 'Slide 1: Intro' }));
    expect(item('Move up').hasAttribute('disabled')).toBe(true);
    await click(item('Move down'));
    expect(api.moveSlide).toHaveBeenCalledWith(7, 1, 2);
    expect(screen.getByRole('button', { name: 'Slide 2: Intro' }).getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('where').textContent).toBe('/deck/7?slide=2');
  });

  it('duplicates a slide and opens the copy', async () => {
    const [a, b, c] = DECK.slides;
    vi.mocked(api.duplicateSlide).mockResolvedValue({ ...b, n: 3 });
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Actions for slide 2' }));
    vi.mocked(api.getDeck).mockResolvedValue(renumber([a, b, b, c]));
    await click(item('Duplicate'));
    expect(api.duplicateSlide).toHaveBeenCalledWith(7, 2);
    expect(screen.getByTestId('where').textContent).toBe('/deck/7?slide=3');
    expect(screen.getByText('3 / 4')).toBeTruthy();
  });

  it('edits a slide in the drawer, saving only what changed', async () => {
    vi.mocked(api.updateSlide).mockResolvedValue(DECK.slides[1]);
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Actions for slide 2' }));
    await click(item('Edit slide…'));
    const drawer = screen.getByRole('dialog', { name: 'Edit slide 2' });
    fireEvent.change(within(drawer).getByLabelText('Body'), { target: { value: 'Step one' } });
    await click(within(drawer).getByRole('button', { name: 'Save slide' }));
    expect(api.updateSlide).toHaveBeenCalledWith(7, 2, { body: 'Step one' });
  });

  it('inserts a new slide after this one', async () => {
    vi.mocked(api.addSlide).mockResolvedValue({ ...DECK.slides[1], n: 2, title: 'New' });
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Actions for slide 1' }));
    await click(item('Insert slide after'));
    const drawer = screen.getByRole('dialog', { name: 'New slide after 1' });
    fireEvent.change(within(drawer).getByLabelText('Title'), { target: { value: 'New' } });
    await click(within(drawer).getByRole('button', { name: 'Add slide' }));
    expect(api.addSlide).toHaveBeenCalledWith(7, { title: 'New', at: 2 });
  });

});

describe('slide rail deletes and permissions', () => {
  it('deletes a slide after confirming and opens the one before', async () => {
    const [a, , c] = DECK.slides;
    vi.mocked(api.deleteSlide).mockResolvedValue(renumber([a, c]));
    renderApp('/deck/7?slide=2');
    await click(await screen.findByRole('button', { name: 'Actions for slide 2' }));
    await click(item('Delete'));
    await click(within(screen.getByRole('dialog', { name: 'Delete slide 2?' })).getByRole('button', { name: 'Delete slide' }));
    expect(api.deleteSlide).toHaveBeenCalledWith(7, 2);
    expect(screen.getByTestId('where').textContent).toBe('/deck/7?slide=1');
  });

  it('offers no slide menu and no download to a visitor', async () => {
    vi.mocked(api.getDeck).mockResolvedValue({ ...structuredClone(DECK), file_id: 'f1' });
    renderApp('/d/7', VISITOR);
    await screen.findByTitle('Slide 1');
    expect(screen.queryByRole('button', { name: 'Actions for slide 1' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Download original' })).toBeNull();
  });

  it('links the original upload for signed-in people', async () => {
    vi.mocked(api.getDeck).mockResolvedValue({ ...structuredClone(DECK), file_id: 'f1' });
    renderApp('/deck/7');
    expect((await screen.findByRole('link', { name: 'Download original' })).getAttribute('href')).toBe('/api/decks/7/original');
  });
});

describe('SlideFrame', () => {
  const shell = '<html><head><script src="reveal.js"></script></head><body><div class="slides"><!--lectern-slide--></div></body></html>';

  it('puts the slide inside the deck shell', () => {
    render(<SlideFrame slide={DECK.slides[0]} shell={shell} />);
    const doc = screen.getByTitle('Slide 1').getAttribute('srcdoc')!;
    expect(doc).toContain('<div class="slides"><section><h1 data-lectern-id="s1.title">Intro</h1></section></div>');
    expect(doc).toContain('reveal.js');
    expect(doc).not.toContain('<!--lectern-slide-->');
  });

  it('keeps the slide alone without a shell, and appends the pick script in pick mode', () => {
    expect(slideDoc('<p>$&</p>', null)).toBe('<p>$&</p>');
    expect(slideDoc('<p>$&</p>', shell)).toContain('<div class="slides"><p>$&</p></div>');
    expect(slideDoc('<p>x</p>', shell, true)).toMatch(/<\/html><style>.*lecternPick/);
  });
});
