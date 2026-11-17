import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { fakeDeckServer } from '../test/fakeDeckServer';
import { renderApp } from '../test/render';

vi.mock('../api', () => import('../test/apiMock'));

beforeEach(() => {
  vi.clearAllMocks();
  fakeDeckServer();
});

const counter = () => screen.getByLabelText(/^Slide \d of 3$/).textContent;
const key = (k: string) => act(() => fireEvent.keyDown(window, { key: k }));

describe('present mode', () => {
  it('moves with the keyboard and leaves with Esc', async () => {
    renderApp('/deck/7/present');
    await screen.findByTitle('Slide 1');
    await act(async () => undefined); // let the key listener's effect run
    expect(counter()).toBe('1 / 3');
    key('ArrowRight');
    expect(counter()).toBe('2 / 3');
    key(' ');
    expect(counter()).toBe('3 / 3');
    key('ArrowRight');
    expect(counter()).toBe('3 / 3');
    key('Home');
    expect(counter()).toBe('1 / 3');
    key('End');
    key('ArrowLeft');
    expect(counter()).toBe('2 / 3');
    key('n');
    expect(screen.getByLabelText('Presenter notes').textContent).toBe('No presenter notes.');
    key('Escape');
    expect(screen.getByTestId('where').textContent).toBe('/deck/7?slide=2');
  });

  it('lets the audience ask the slide on screen; Esc closes the drawer first', async () => {
    renderApp('/d/7/present?slide=3');
    await screen.findByText('Risks');
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Ask' })));
    const drawer = screen.getByRole('dialog', { name: 'Ask slide 3' });
    fireEvent.change(within(drawer).getByLabelText('Question'), { target: { value: 'Why?' } });
    await act(async () => fireEvent.click(within(drawer).getByRole('button', { name: 'Ask' })));
    expect(api.ask).toHaveBeenCalledWith(7, 3, 'Why?');
    expect(await within(drawer).findByText('Answer to "Why?" on 3.')).toBeTruthy();
    act(() => fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/d/7/present?slide=3');
  });
});
