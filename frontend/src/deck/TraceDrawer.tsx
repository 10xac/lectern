import { useCallback } from 'react';
import { api } from '../api';
import { ErrorText } from '../components/ui/ErrorText';
import { Drawer } from '../components/ui/Overlay';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useLoad } from '../lib/useLoad';

/** One graph run step by step: node, outcome, block ids, milliseconds. */
export function TraceDrawer({ traceId, onClose }: { traceId: number; onClose: () => void }) {
  const { data: trace, error } = useLoad(useCallback(() => api.getTrace(traceId), [traceId]));
  return (
    <Drawer title={`Trace ${traceId}`} onClose={onClose} size="lg">
      <ErrorText>{error}</ErrorText>
      {trace && (
        <>
          <p className="mb-4 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
            <StatusBadge tone="info">{trace.template}</StatusBadge>
            <span className="font-mono text-xs">{trace.agent}</span>
            <StatusBadge tone={trace.outcome === 'done' ? 'success' : 'warning'}>{trace.outcome}</StatusBadge>
          </p>
          <ol className="relative space-y-3 border-l border-line pl-5">
            {trace.steps.map((s) => (
              <li key={s.index} className="relative">
                <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-brand bg-surface" aria-hidden />
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-medium text-ink-strong">{s.node}</span>
                  <span className="text-xs text-ink-muted">{s.outcome}</span>
                  {s.ms != null && <span className="ml-auto text-xs tabular-nums text-ink-faint">{s.ms} ms</span>}
                </div>
                {s.block_ids.length > 0 && <p className="mt-0.5 break-all font-mono text-xs text-ink-soft">{s.block_ids.join(' ')}</p>}
              </li>
            ))}
          </ol>
        </>
      )}
    </Drawer>
  );
}
