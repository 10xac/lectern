import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type ModelSettings } from '../api';
import { LOCAL, MEMBER, renderApp } from '../test/render';

vi.mock('../api', () => import('../test/apiMock'));

const click = async (el: HTMLElement) => act(async () => fireEvent.click(el));
const SETTINGS: ModelSettings = {
  settings: [{ name: 'LECTERN_PROVIDER', value: 'fake', source: 'env' }, { name: 'LECTERN_MODEL', value: '', source: 'unset' }],
  keys: [
    { name: 'LECTERN_API_KEY', set: true, source: 'lectern', last4: 'abcd' },
    { name: 'EXA_API_KEY', set: false, source: 'unset', last4: null },
  ],
  store_configured: true,
  system1: { kind: 'rules', provider: null, model: null, key: '', why: 'no System1 key' },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.users).mockResolvedValue([
    { id: 1, email: 'ada@example.org', role: 'admin', status: 'active' },
    { id: 3, email: 'cy@example.org', role: 'member', status: 'active' },
  ]);
  vi.mocked(api.modelSettings).mockResolvedValue(SETTINGS);
  vi.mocked(api.putSetting).mockResolvedValue(SETTINGS);
  vi.mocked(api.tokens).mockResolvedValue([]);
  vi.mocked(api.connections).mockResolvedValue([{ id: 'g1', user_id: 1, email: 'ada@example.org', client: 'claude.ai', created_at: 1, last_used_at: null }]);
  vi.mocked(api.endConnection).mockResolvedValue(undefined);
});

describe('users', () => {
  it('invites someone and shows the one-time link', async () => {
    vi.mocked(api.invite).mockResolvedValue({ user: { id: 4, email: 'new@example.org', role: 'member', status: 'invited' }, invite_url: 'http://x/#invite=abc' });
    renderApp('/people/users');
    await click(await screen.findByRole('button', { name: 'Invite user' }));
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@example.org' } });
    await click(screen.getByRole('button', { name: 'Create invite link' }));
    expect(api.invite).toHaveBeenCalledWith('new@example.org', 'member');
    expect(screen.getByRole('status', { name: 'invite link' }).textContent).toContain('http://x/#invite=abc');
  });

  it('disables a user only after confirming', async () => {
    vi.mocked(api.updateUser).mockResolvedValue({ id: 3, email: 'cy@example.org', role: 'member', status: 'disabled' });
    renderApp('/people/users');
    const row = (await screen.findByText('cy@example.org')).closest('tr')!;
    await click(within(row).getByRole('button', { name: 'Disable' }));
    expect(api.updateUser).not.toHaveBeenCalled();
    await click(within(screen.getByRole('dialog', { name: 'Disable cy@example.org?' })).getByRole('button', { name: 'Disable' }));
    expect(api.updateUser).toHaveBeenCalledWith(3, { status: 'disabled' });
  });

  it('is for admins only', async () => {
    renderApp('/people/users', MEMBER);
    expect(await screen.findByText('Admins only')).toBeTruthy();
    expect(api.users).not.toHaveBeenCalled();
  });
});

describe('models and keys', () => {
  it('never shows a key, rotates it and removes a stored one', async () => {
    renderApp('/platform/models');
    expect(await screen.findByText('configured ••••abcd (lectern)')).toBeTruthy();
    const input = screen.getByLabelText('New value for LECTERN_API_KEY') as HTMLInputElement;
    expect(input.type).toBe('password');
    expect(input.value).toBe('');
    fireEvent.change(input, { target: { value: 'sk-new' } });
    const row = input.closest('div.grid') as HTMLElement;
    await click(within(row).getByRole('button', { name: 'Save' }));
    expect(api.putSetting).toHaveBeenCalledWith('LECTERN_API_KEY', 'sk-new');
    expect(input.value).toBe('');
    await click(within(row).getByRole('button', { name: 'Remove' }));
    await click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    expect(api.putSetting).toHaveBeenLastCalledWith('LECTERN_API_KEY', null);
    const exa = screen.getByLabelText('New value for EXA_API_KEY').closest('div.grid') as HTMLElement;
    expect(within(exa).queryByRole('button', { name: 'Remove' })).toBeNull();
  });

  it('explains when keys cannot be stored', async () => {
    vi.mocked(api.modelSettings).mockResolvedValue({ ...SETTINGS, store_configured: false });
    renderApp('/platform/models');
    expect(await screen.findByText(/Keys cannot be stored here yet/)).toBeTruthy();
    expect((screen.getByLabelText('New value for EXA_API_KEY') as HTMLInputElement).disabled).toBe(true);
  });
});

describe('MCP tokens and connections', () => {
  it('shows a new token once, with ready-to-paste instructions', async () => {
    vi.mocked(api.createToken).mockResolvedValue({ token: { id: 't1', name: 'laptop', created_at: 1, expires_at: 2, revoked_at: null, last_used_at: null }, secret: 'lectern_pat_SECRET' });
    renderApp('/connect/tokens');
    await click(await screen.findByRole('button', { name: 'New token' }));
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'laptop' } });
    await click(screen.getByRole('button', { name: 'Create token' }));
    expect(api.createToken).toHaveBeenCalledWith('laptop', 30);
    expect(screen.getByRole('status', { name: 'token' }).textContent).toContain('Copy it now: it is not shown again.');
    expect(screen.getByText(/claude mcp add --transport http lectern .*\/mcp\/ --header "Authorization: Bearer lectern_pat_SECRET"/)).toBeTruthy();
  });

  it('explains tokens and connections when login is off', async () => {
    renderApp('/connect/tokens', LOCAL);
    expect(await screen.findByText('Login is off')).toBeTruthy();
    expect(api.tokens).not.toHaveBeenCalled();
  });

  it('disconnects an app after confirming', async () => {
    renderApp('/connect/connections');
    await click(await screen.findByRole('button', { name: 'Disconnect' }));
    await click(within(screen.getByRole('dialog', { name: 'Disconnect claude.ai?' })).getByRole('button', { name: 'Disconnect' }));
    expect(api.endConnection).toHaveBeenCalledWith('g1');
  });
});
