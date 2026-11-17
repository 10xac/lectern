import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { useState } from 'react';
import { api, type Confidence as Conf } from '../api';
import { StatusBadge } from '../components/ui/StatusBadge';
import type { Tone } from '../components/ui/styles';
import { cn } from '../lib/cn';

const NAMES: Record<string, string> = { K: 'deck', M: 'memory', W: 'web', P: 'model' };
const VERDICT: Record<Conf['verdict'], Tone> = { answer: 'success', qualify: 'warning', ask: 'info', abstain: 'neutral' };
const pct = (x: number) => `${Math.round(x * 100)}%`;

/** One chip per consulted source and one for the fused answer; hover for r, g, Z and κ. */
export function ConfidenceChips({ confidence }: { confidence: Conf }) {
  const { fusion, triage } = confidence;
  return (
    <div className="flex flex-wrap items-center gap-1" aria-label="Confidence">
      <StatusBadge tone={VERDICT[confidence.verdict] ?? 'neutral'} title={`${confidence.why} · triage (${triage.by}): ${triage.class}`}>
        {confidence.verdict}
      </StatusBadge>
      {fusion && (
        <StatusBadge tone="brand" title={`P(best) ${fusion.p_best} · Z ${fusion.z} · κ ${fusion.kappa}`}>fused {pct(fusion.p_best)}</StatusBadge>
      )}
      {confidence.sources.map((s) => (
        <StatusBadge key={s.source} tone={s.status === 'done' ? 'info' : 'neutral'} title={`r ${s.r} · g ${s.g}${s.reason ? ` · ${s.reason}` : ''}`}>
          {NAMES[s.source] ?? s.source} {s.status === 'done' ? pct(s.r * (1 - s.g)) : s.status}
        </StatusBadge>
      ))}
    </div>
  );
}

/** 👍/👎 on an answer: tells the job's calibration whether it was right. */
export function Votes({ jobId }: { jobId: string }) {
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const send = (v: 'up' | 'down') => {
    setVote(v);
    void api.feedback(jobId, v).catch(() => setVote(null));
  };
  const look = (on: boolean) => cn('rounded p-1 hover:bg-surface-hover', on ? 'text-brand' : 'text-ink-muted');
  return (
    <span className="inline-flex gap-0.5">
      <button type="button" aria-label="Good answer" aria-pressed={vote === 'up'} className={look(vote === 'up')} onClick={() => send('up')}>
        <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button type="button" aria-label="Bad answer" aria-pressed={vote === 'down'} className={look(vote === 'down')} onClick={() => send('down')}>
        <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
      </button>
    </span>
  );
}
