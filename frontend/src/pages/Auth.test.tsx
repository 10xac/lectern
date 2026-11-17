import { act, fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api';
import { browser } from '../lib/browser';
import { ADMIN, renderApp, VISITOR } from '../test/render';

vi.mock('../api', () => import('../test/apiMock'));

const where = () => screen.getByTestId('where').textContent;
const type = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const click = async (name: string) => act(async () => fireEvent.click(screen.getByRole('button', { name })));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listDecks).mockResolvedValue([]);
  vi.mocked(api.tokens).mockResolvedValue([]);
});

describe('sign in', () => {
  it('sends a signed-out visitor to /login and back after signing in', async () => {
    vi.mocked(api.login).mockResolvedValue({ user: ADMIN.user!, csrf: 'tok' });
    renderApp('/connect/tokens', VISITOR);
    await screen.findByRole('form', { name: 'Sign in' });
    expect(where()).toBe('/login?next=%2Fconnect%2Ftokens');
    type('Email', 'ada@example.org');
    type('Password', 'a long password');
    await click('Sign in');
    expect(api.login).toHaveBeenCalledWith('ada@example.org', 'a long password');
    expect(where()).toBe('/connect/tokens');
  });

  it('shows a failed sign-in and never follows an off-site next', async () => {
    vi.mocked(api.login).mockRejectedValueOnce(new ApiError('wrong email or password', 401));
    renderApp('/login?next=//evil.example', VISITOR);
    await screen.findByRole('form', { name: 'Sign in' });
    type('Email', 'ada@example.org');
    type('Password', 'nope nope nope');
    await click('Sign in');
    expect(screen.getByRole('alert').textContent).toBe('wrong email or password');
    vi.mocked(api.login).mockResolvedValue({ user: ADMIN.user!, csrf: 'tok' });
    await click('Sign in');
    expect(where()).toBe('/');
  });
});

describe('accept invite', () => {
  it('turns a legacy /#invite= link into the invite page and checks the password', async () => {
    vi.mocked(api.acceptInvite).mockResolvedValue({ user: ADMIN.user!, csrf: 'tok' });
    renderApp('/#invite=tok-123', VISITOR);
    await screen.findByRole('form', { name: 'Choose a password' });
    expect(where()).toBe('/accept-invite#invite=tok-123');
    type('Password', 'short');
    type('Repeat password', 'short');
    await click('Set password');
    expect(screen.getByRole('alert').textContent).toContain('at least 12');
    expect(api.acceptInvite).not.toHaveBeenCalled();
    type('Password', 'a much longer one');
    type('Repeat password', 'a much longer one');
    await click('Set password');
    expect(api.acceptInvite).toHaveBeenCalledWith('tok-123', 'a much longer one');
    expect(where()).toBe('/');
  });
});

describe('OAuth consent', () => {
  it('asks a signed-out person to sign in first', async () => {
    renderApp('/connect/authorize?txn=t1', VISITOR);
    await screen.findByRole('form', { name: 'Sign in' });
    expect(where()).toBe('/login?next=%2Fconnect%2Fauthorize%3Ftxn%3Dt1');
  });

  it.each([[true, 'Approve'], [false, 'Deny']])('completes with approve=%s and leaves for the client', async (approve, button) => {
    const assign = vi.spyOn(browser, 'assign').mockImplementation(() => undefined);
    vi.mocked(api.consent).mockResolvedValue({ client: 'claude.ai', redirect_host: 'claude.ai', scopes: ['lectern'] });
    vi.mocked(api.completeConsent).mockResolvedValue({ redirect_to: 'https://claude.ai/cb?code=x' });
    renderApp('/connect/authorize?txn=t1', ADMIN);
    expect((await screen.findByLabelText('Consent')).textContent).toContain('claude.ai wants to use lectern as ada@example.org');
    await click(button);
    expect(api.consent).toHaveBeenCalledWith('t1');
    expect(api.completeConsent).toHaveBeenCalledWith('t1', approve);
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=x');
  });

  it('explains an expired or foreign request', async () => {
    vi.mocked(api.consent).mockRejectedValue(new ApiError('this sign-in request was opened in another browser', 403));
    renderApp('/connect/authorize?txn=t1', ADMIN);
    expect(await screen.findByText('This request cannot continue')).toBeTruthy();
    expect(screen.getByText(/opened in another browser/)).toBeTruthy();
  });
});
