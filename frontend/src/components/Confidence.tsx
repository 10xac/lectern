import { useState } from 'react';
import { api, type Confidence as Conf } from '../api';

const NAMES: Record<string, string> = { K: 'deck', M: 'memory', W: 'web', P: 'model' };
const pct = (x: number) => `${Math.round(x * 100)}%`;

/** One chip per consulted source and one for the fused answer; hover for r, g, Z and κ. */
export function ConfidenceChips({ confidence, jobId }: { confidence: Conf; jobId?: string | null }) {
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const { fusion, triage } = confidence;
  const send = (v: 'up' | 'down') => {
    if (!jobId) return;
    setVote(v);
    void api.feedback(jobId, v).catch(() => setVote(null));
  };
  return (
    <div className="confidence" aria-label="Confidence">
      <span className={`chip verdict ${confidence.verdict}`} title={`${confidence.why} · triage (${triage.by}): ${triage.class}`}>
        {confidence.verdict}
      </span>
      {fusion && (
        <span className="chip fused" title={`P(best) ${fusion.p_best} · Z ${fusion.z} · κ ${fusion.kappa}`}>
          fused {pct(fusion.p_best)}
        </span>
      )}
      {confidence.sources.map((s) => (
        <span
          key={s.source}
          className={`chip source ${s.status}`}
          title={`r ${s.r} · g ${s.g}${s.reason ? ` · ${s.reason}` : ''}`}
        >
          {NAMES[s.source] ?? s.source} {s.status === 'done' ? pct(s.r * (1 - s.g)) : s.status}
        </span>
      ))}
      {jobId && (
        <span className="votes">
          <button type="button" aria-label="Good answer" aria-pressed={vote === 'up'} onClick={() => send('up')}>
            👍
          </button>
          <button type="button" aria-label="Bad answer" aria-pressed={vote === 'down'} onClick={() => send('down')}>
            👎
          </button>
        </span>
      )}
    </div>
  );
}
