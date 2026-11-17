import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api';
import { DECK } from '../test/deck';
import { fakeDeckServer } from '../test/fakeDeckServer';
import { renderApp, VISITOR } from '../test/render';

vi.mock('../api', () => import('../test/apiMock'));

beforeEach(() => {
  vi.clearAllMocks();
  fakeDeckServer();
  vi.mocked(api.updateSlide).mockResolvedValue(DECK.slides[0]);
});

const click = async (el: HTMLElement) => act(async () => fireEvent.click(el));
const button = (name: string | RegExp) => screen.getByRole('button', { name });

describe('sharing', () => {
  it('makes a deck password-protected and shows its link', async () => {
    vi.mocked(api.sharing).mockResolvedValue({ visibility: 'private', has_password: false });
    vi.mocked(api.share).mockResolvedValue({ visibility: 'password', has_password: true });
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Share' }));
    const dialog = screen.getByRole('dialog', { name: 'Share deck' });
    fireEvent.click(within(dialog).getByLabelText(/^Password/, { selector: 'input[type=radio]' }));
    fireEvent.change(within(dialog).getByLabelText('Password', { selector: 'input[type=password]' }), { target: { value: 'pw1234' } });
    expect(within(dialog).getByText(`${window.location.origin}/d/7`)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(api.share).toHaveBeenCalledWith(7, 'password', 'pw1234');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getAllByText('password').length).toBeGreaterThan(0);
  });
});

describe('slide notes and titles', () => {
  it('edits the presenter notes of the current slide', async () => {
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Show notes' }));
    expect(screen.getByText('Say hi')).toBeTruthy();
    await click(button('Edit notes'));
    fireEvent.change(screen.getByLabelText('Notes for slide 1'), { target: { value: 'Say hello' } });
    await click(button('Save notes'));
    expect(api.updateSlide).toHaveBeenCalledWith(7, 1, { notes: 'Say hello' });
    expect(screen.getByText('Say hello')).toBeTruthy();
  });

  it('renames a slide in place', async () => {
    renderApp('/deck/7');
    await click(await screen.findByRole('button', { name: 'Rename slide' }));
    fireEvent.change(screen.getByLabelText('Slide title'), { target: { value: 'Welcome' } });
    await click(button('Save title'));
    expect(api.updateSlide).toHaveBeenCalledWith(7, 1, { title: 'Welcome' });
    expect(screen.getByRole('button', { name: 'Slide 1: Welcome' })).toBeTruthy();
  });

  it('edits the notes of several selected slides (shift-click selects a range)', async () => {
    renderApp('/deck/7');
    fireEvent.click(await screen.findByLabelText('Select slide 1'));
    fireEvent.click(screen.getByLabelText('Select slide 3'), { shiftKey: true });
    expect(screen.getByRole('toolbar', { name: 'Selected slides' }).textContent).toContain('3 selected');
    await click(button('Edit notes'));
    const drawer = screen.getByRole('dialog', { name: 'Notes for 3 slides' });
    fireEvent.change(within(drawer).getByLabelText('Notes for slide 2'), { target: { value: 'New plan notes' } });
    await click(within(drawer).getByRole('button', { name: 'Save notes' }));
    expect(api.updateSlide).toHaveBeenCalledTimes(1);
    expect(api.updateSlide).toHaveBeenCalledWith(7, 2, { notes: 'New plan notes' });
  });
});

describe('a visitor on a shared link', () => {
  it('unlocks a password deck and sees it read-only', async () => {
    vi.mocked(api.getDeck).mockRejectedValueOnce(new ApiError('log in first', 401));
    vi.mocked(api.listDecks).mockResolvedValue([{ id: 7, title: 'Test deck', source: 'html', visibility: 'password' }]);
    vi.mocked(api.unlock).mockResolvedValue({ unlocked: true });
    renderApp('/d/7', VISITOR);
    fireEvent.change(await screen.findByLabelText('Deck password'), { target: { value: 'pw1234' } });
    await click(button('Unlock'));
    expect(api.unlock).toHaveBeenCalledWith(7, 'pw1234');
    expect(await screen.findByTitle('Slide 1')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Share' })).toBeNull();
    expect(screen.queryByLabelText('Select slide 1')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Rename slide' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeTruthy();
  });

  it('sends a visitor to sign in when the deck is private', async () => {
    vi.mocked(api.getDeck).mockRejectedValue(new ApiError('log in first', 401));
    vi.mocked(api.listDecks).mockResolvedValue([]);
    renderApp('/d/7', VISITOR);
    await screen.findByRole('form', { name: 'Sign in' });
    expect(screen.getByTestId('where').textContent).toBe('/login?next=%2Fd%2F7');
  });
});

