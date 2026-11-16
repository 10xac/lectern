import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { api, type Confidence } from '../api';
import { ConfidenceChips } from './Confidence';

vi.mock('../api', () => ({ api: { feedback: vi.fn(async () => ({})) } }));

const CONF: Confidence = {
  verdict: 'qualify',
  why: 'sources disagree (κ = 0.72)',
  triage: { by: 'rules', class: 'rare', engage: 0.95, hops: 1, note: '' },
  fusion: { best: 'a', p_best: 0.61, z: 0.07, kappa: 0.72 },
  sources: [
    { source: 'K', status: 'done', r: 0.9, g: 0.2, reason: '' },
    { source: 'W', status: 'done', r: 0.8, g: 0.3, reason: '' },
    { source: 'P', status: 'skipped', r: 0, g: 1, reason: 'the fake model has no knowledge of its own' },
  ],
};

describe('ConfidenceChips', () => {
  it('shows the verdict, the fused figure and one chip per source with r, g, Z and κ on hover', () => {
    render(<ConfidenceChips confidence={CONF} jobId="j1" />);
    expect(screen.getByText('qualify').getAttribute('title')).toContain('sources disagree');
    expect(screen.getByText('fused 61%').getAttribute('title')).toBe('P(best) 0.61 · Z 0.07 · κ 0.72');
    expect(screen.getByText('deck 72%').getAttribute('title')).toBe('r 0.9 · g 0.2');
    expect(screen.getByText('model skipped').getAttribute('title')).toContain('no knowledge');
  });

  it('sends feedback on the job', () => {
    render(<ConfidenceChips confidence={CONF} jobId="j1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Good answer' }));
    expect(api.feedback).toHaveBeenCalledWith('j1', 'up');
    expect(screen.getByRole('button', { name: 'Good answer' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('has no vote buttons without a job and no fused chip without a fusion', () => {
    render(<ConfidenceChips confidence={{ ...CONF, fusion: null }} />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByText(/fused/)).toBeNull();
  });
});
