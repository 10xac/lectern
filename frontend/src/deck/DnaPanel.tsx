import { useEffect, useState } from 'react';
import { api, type DnaGraph as Graph } from '../api';
import { EmptyState } from '../components/ui/EmptyState';
import { cn } from '../lib/cn';
import { DnaGraph, DnaLegend } from './DnaGraph';
import { FilesCheck } from './FilesCheck';

/** "(high) … [dna:ab12]" lines, with each [dna:id] turned into a button that opens the record. */
function TraceText({ text, onOpen }: { text: string; onOpen: (id: string) => void }) {
  if (!text.trim()) return <EmptyState title="No DNA yet" description="Add an influence to record what shaped this slide." className="py-6" />;
  return (
    <ol className="space-y-1.5 font-mono text-xs leading-5 text-ink" aria-label="DNA text">
      {text.split('\n').map((line, i) => (
        <li key={i} className="whitespace-pre-wrap">
          {line.split(/(\[dna:\w+\])/).map((part, j) => {
            const m = /^\[dna:(\w+)\]$/.exec(part);
            return m ? (
              <button key={j} type="button" onClick={() => onOpen(m[1])} className="mx-0.5 rounded border border-brand/30 bg-brand-soft px-1.5 font-sans text-brand hover:bg-brand hover:text-white">open</button>
            ) : part;
          })}
        </li>
      ))}
    </ol>
  );
}

function Toggle<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded border border-line bg-surface p-0.5">
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={cn('rounded-sm px-2.5 py-0.5 text-xs', value === v ? 'bg-brand text-white' : 'text-ink-soft hover:text-ink')}>
          {text}
        </button>
      ))}
    </div>
  );
}

interface Props {
  deckId: number;
  slide: number;
  version: number;
  onOpen: (influenceId: string) => void;
  admin?: boolean;
}

/** The conceptual DNA of this slide or of the whole deck, as a graph or as an ordered trace. */
export function DnaPanel({ deckId, slide, version, onOpen, admin = false }: Props) {
  const [view, setView] = useState<'graph' | 'text'>('graph');
  const [scope, setScope] = useState<'slide' | 'deck'>('slide');
  const [graph, setGraph] = useState<Graph | null>(null);
  const [text, setText] = useState('');
  const target = scope === 'deck' ? undefined : slide;
  useEffect(() => {
    void api.dnaGraph(deckId, target).then(setGraph, () => setGraph(null));
    void api.dnaText(deckId, target).then((t) => setText(t.text), () => setText(''));
  }, [deckId, target, version]);
  const empty = graph && !graph.nodes.some((n) => n.type === 'influence');
  return (
    <section aria-label="DNA" className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Toggle label="View" value={view} onChange={setView} options={[['graph', 'Graph'], ['text', 'Text']]} />
        <Toggle label="Scope" value={scope} onChange={setScope} options={[['slide', `Slide ${slide}`], ['deck', 'Whole deck']]} />
      </div>
      {view === 'graph' && graph && (
        <div className="rounded-lg border border-line-soft bg-surface-muted p-2">
          <DnaGraph graph={graph} onOpen={onOpen} />
          <DnaLegend />
          {empty && <p className="mt-2 text-xs text-ink-muted">No influences recorded here yet.</p>}
        </div>
      )}
      {view === 'text' && <TraceText text={text} onOpen={onOpen} />}
      {admin && <FilesCheck />}
    </section>
  );
}
