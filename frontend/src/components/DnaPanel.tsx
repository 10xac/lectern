import { useEffect, useState } from 'react';
import { api, type DnaGraph as Graph, type Reconciled } from '../api';
import { DnaGraph } from './DnaGraph';

/** "(high) … [dna:ab12]" lines, with each [dna:id] turned into a button that opens the record. */
function TraceText({ text, onOpen }: { text: string; onOpen: (id: string) => void }) {
  return (
    <ol className="dna-text">
      {text.split('\n').map((line, i) => (
        <li key={i}>
          {line.split(/(\[dna:\w+\])/).map((part, j) => {
            const m = /^\[dna:(\w+)\]$/.exec(part);
            return m ? <button key={j} type="button" className="chip" onClick={() => onOpen(m[1])}>open</button> : part;
          })}
        </li>
      ))}
    </ol>
  );
}

/** Files whose contents vanished: relink each to a file in the store, or delete its metadata. */
export function FilesCheck() {
  const [found, setFound] = useState<Reconciled | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const check = async () => {
    const r = await api.reconcile();
    setFound(r);
    setChoice(r.suggestions);
  };
  const act = async (p: Promise<unknown>) => {
    await p;
    await check();
  };
  return (
    <section className="files-check" aria-label="Unlinked files">
      <button type="button" onClick={() => void check()}>Check files</button>
      {found && found.missing.length === 0 && <span className="muted"> All files are linked.</span>}
      <ul>
        {found?.missing.map((f) => (
          <li key={f.id}>
            {f.path} is missing.{' '}
            <select aria-label={`New file for ${f.path}`} value={choice[f.id] ?? ''} onChange={(e) => setChoice({ ...choice, [f.id]: e.target.value })}>
              <option value="">Relink to file…</option>
              {found.unregistered.map((p) => <option key={p}>{p}</option>)}
            </select>
            <button type="button" disabled={!choice[f.id]} onClick={() => void act(api.relink(f.id, choice[f.id]))}>Relink</button>
            <button type="button" onClick={() => void act(api.forget(f.id))}>Delete metadata</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface Props {
  deckId: number;
  slide: number;
  version: number;
  onOpen: (influenceId: string) => void;
}

/** The conceptual DNA of this slide or of the whole deck, as a graph or as an ordered trace. */
export function DnaPanel({ deckId, slide, version, onOpen }: Props) {
  const [view, setView] = useState<'visual' | 'text'>('visual');
  const [whole, setWhole] = useState(false);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [text, setText] = useState('');
  const target = whole ? undefined : slide;
  useEffect(() => {
    void api.dnaGraph(deckId, target).then(setGraph, () => setGraph(null));
    void api.dnaText(deckId, target).then((t) => setText(t.text), () => setText(''));
  }, [deckId, target, version]);
  return (
    <section className="dna" aria-label="DNA">
      <div className="tabs">
        <button type="button" aria-pressed={view === 'visual'} onClick={() => setView('visual')}>Visual</button>
        <button type="button" aria-pressed={view === 'text'} onClick={() => setView('text')}>Text</button>
        <label><input type="checkbox" checked={whole} onChange={(e) => setWhole(e.target.checked)} /> whole deck</label>
      </div>
      {view === 'visual' ? graph && <DnaGraph graph={graph} onOpen={onOpen} /> : <TraceText text={text} onOpen={onOpen} />}
      <FilesCheck />
    </section>
  );
}
