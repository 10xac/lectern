import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { LOCAL, MEMBER, renderApp } from '../test/render';

vi.mock('../api', () => import('../test/apiMock'));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listDecks).mockResolvedValue([{ id: 7, title: 'Test deck', source: 'html', visibility: 'public' }]);
  vi.mocked(api.logout).mockResolvedValue(undefined);
});

describe('the app shell', () => {
  it('lists decks as links with their visibility', async () => {
    renderApp('/');
    const link = await screen.findByRole('link', { name: /Test deck/ });
    expect(link.getAttribute('href')).toBe('/deck/7');
    expect(within(link).getByText('public')).toBeTruthy();
  });

  it('hides admin pages from members and signs out from the account menu', async () => {
    renderApp('/', MEMBER);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'MCP tokens' })).toBeTruthy();
    expect(within(nav).queryByRole('link', { name: 'Users' })).toBeNull();
    expect(within(nav).queryByRole('link', { name: 'Models & keys' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByRole('menu').textContent).toContain('bob@example.org');
    await act(async () => fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' })));
    expect(api.logout).toHaveBeenCalled();
    expect(screen.getByTestId('where').textContent).toBe('/login');
  });

  it('shows everything without a login when login is off', async () => {
    renderApp('/login', LOCAL);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Models & keys' })).toBeTruthy();
    expect(screen.getByTestId('where').textContent).toBe('/');
  });

  it('folds a nav group and collapses the sider', async () => {
    renderApp('/');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    fireEvent.click(within(nav).getByRole('button', { name: 'Connect' }));
    expect(within(nav).queryByRole('link', { name: 'MCP tokens' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }));
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeTruthy();
  });
});
