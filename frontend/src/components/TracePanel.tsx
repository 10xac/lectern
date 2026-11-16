import { useEffect, useState } from 'react';
import { api, type Trace } from '../api';

interface Props {
  traceId: number;
  onClose: () => void;
}

/** A drawer that shows one graph run step by step: node, outcome, block ids, milliseconds. */
export function TracePanel({ traceId, onClose }: Props) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .getTrace(traceId)
      .then((t) => live && setTrace(t))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [traceId]);

  return (
    <aside className="drawer" role="dialog" aria-label={`Trace ${traceId}`}>
      <header>
        <h2>Trace {traceId}</h2>
        <button type="button" onClick={onClose} aria-label="Close trace">
          ×
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {trace && (
        <>
          <p>
            {trace.template} · {trace.agent} · <strong>{trace.outcome}</strong>
          </p>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>node</th>
                <th>outcome</th>
                <th>blocks</th>
                <th>ms</th>
              </tr>
            </thead>
            <tbody>
              {trace.steps.map((s) => (
                <tr key={s.index}>
                  <td>{s.index}</td>
                  <td>{s.node}</td>
                  <td>{s.outcome}</td>
                  <td className="ids">{s.block_ids.join(' ')}</td>
                  <td>{s.ms ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </aside>
  );
}
