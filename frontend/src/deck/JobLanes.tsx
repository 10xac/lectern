import type { LiveJob } from '../hooks/useSlideChat';
import { cn } from '../lib/cn';

const SOURCE_NAMES: Record<string, string> = { K: 'deck', M: 'memory', W: 'web', P: 'model' };
const STATE_LOOK: Record<string, string> = {
  queued: 'border-line bg-surface-sunken text-ink-muted',
  running: 'border-info-line bg-info-soft text-info animate-pulse',
  done: 'border-success-line bg-success-soft text-[#389E0D]',
  failed: 'border-danger-line bg-danger-soft text-danger-ink',
};

/** Running questions, each with its researchers as parallel lanes. */
export function JobLanes({ jobs }: { jobs: LiveJob[] }) {
  if (jobs.length === 0) return null;
  return (
    <ul className="space-y-2" aria-label="Running questions">
      {jobs.map((job) => (
        <li key={job.id} className="rounded-lg border border-line-soft bg-surface-muted p-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-brand" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-ink">{job.question}</span>
            <span className="text-ink-muted">{job.status}…</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-1.5">
            {Object.entries(job.lanes).map(([source, state]) => (
              <span key={source} title={`${SOURCE_NAMES[source] ?? source}: ${state}`}
                className={cn('rounded border px-2 py-0.5 text-center text-xs', STATE_LOOK[state] ?? STATE_LOOK.queued)}>
                {SOURCE_NAMES[source] ?? source} · {state}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
