import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { Account } from './Account';
import { inviteToken, Login } from './Login';

vi.mock('../api', () => ({
  api: {
    login: vi.fn(), acceptInvite: vi.fn(), tokens: vi.fn(async () => []), users: vi.fn(async () => []),
    createToken: vi.fn(async () => ({ token: {}, secret: 'lectern_pat_shown_once' })), revokeToken: vi.fn(),
    invite: vi.fn(async () => ({ user: {}, invite_url: 'https://h/#invite=abc' })), updateUser: vi.fn(), reinvite: vi.fn(),
    modelSettings: vi.fn(async () => ({
      settings: [{ name: 'LECTERN_MODEL', value: 'm', source: 'environment' }],
      keys: [{ name: 'LECTERN_API_KEY', set: true, source: 'lectern', last4: 'wxyz' }],
      store_configured: true, system1: { kind: 'jev', provider: 'openrouter', model: 'j', key: 'set', why: 'OpenRouter' },
    })),
    putSetting: vi.fn(async () => ({ settings: [], keys: [], store_configured: true, system1: { kind: 'rules', why: '' } })),
  },
}));

const ME = { id: 1, email: 'a@example.org', role: 'admin' as const, status: 'active' as const };
beforeEach(() => vi.clearAllMocks());

describe('Login', () => {
  it('signs in, or sets a password from an invite link', async () => {
    vi.mocked(api.login).mockResolvedValue({ user: ME, csrf: 'c' });
    const onIn = vi.fn();
    const { unmount } = render(<Login invite={null} onIn={onIn} />);
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@example.org' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret secret' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Sign in' })));
    expect(onIn).toHaveBeenCalledWith(ME, 'c');
    unmount();
    vi.mocked(api.acceptInvite).mockRejectedValue(new Error('this invite link is invalid or has expired'));
    render(<Login invite="tok" onIn={onIn} />);
    expect(screen.queryByLabelText('Email')).toBeNull();
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a long password' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Set password' })));
    expect(api.acceptInvite).toHaveBeenCalledWith('tok', 'a long password');
    expect(screen.getByText(/invalid or has expired/)).toBeTruthy();
    expect(inviteToken('#invite=ab-c_1')).toBe('ab-c_1');
    expect(inviteToken('#other')).toBeNull();
  });
});

describe('Account', () => {
  it('shows a new token once, an invite link, and keys only as set', async () => {
    render(<Account user={ME} />);
    fireEvent.change(screen.getByLabelText('Token name'), { target: { value: 'laptop' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Create token' })));
    expect(screen.getByText('lectern_pat_shown_once')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Invite email'), { target: { value: 'b@example.org' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Invite' })));
    expect(api.invite).toHaveBeenCalledWith('b@example.org', 'member');
    expect(screen.getByText('https://h/#invite=abc')).toBeTruthy();
    expect(await screen.findByText('set …wxyz (lectern)')).toBeTruthy();
    expect((screen.getByLabelText('LECTERN_API_KEY') as HTMLInputElement).value).toBe('');
    fireEvent.change(screen.getByLabelText('LECTERN_API_KEY'), { target: { value: 'new-key' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Save' })));
    expect(api.putSetting).toHaveBeenCalledWith('LECTERN_API_KEY', 'new-key');
  });

  it('without login (one local user) shows only the model settings', async () => {
    render(<Account user={null} />);
    expect(await screen.findByRole('region', { name: 'Models and keys' })).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Users' })).toBeNull();
  });
});
