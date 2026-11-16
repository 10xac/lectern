import type { LiveJob } from '../hooks/useSlideChat';

const SOURCE_NAMES: Record<string, string> = { K: 'deck', M: 'memory', W: 'web', P: 'model' };

/** Running jobs on this slide, each with its researchers as parallel lanes. */
export function JobLanes({ jobs }: { jobs: LiveJob[] }) {
  if (jobs.length === 0) return null;
  return (
    <ul className="jobs" aria-label="Running questions">
      {jobs.map((job) => (
        <li key={job.id} className="job">
          <span className="job-question">{job.question}</span>
          <span className="job-status">{job.status}…</span>
          <div className="lanes">
            {Object.entries(job.lanes).map(([source, state]) => (
              <span key={source} className={`lane ${state}`} title={`${SOURCE_NAMES[source] ?? source}: ${state}`}>
                {SOURCE_NAMES[source] ?? source} · {state}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
