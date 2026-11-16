import { useEffect, useState, type FormEvent } from 'react';
import { api, type ComponentKind, type Degree, type Influence, type InfluenceIn, type InfluenceKind, type Ref, type StoredFile } from '../api';

const KINDS: InfluenceKind[] = ['idea', 'reasoning', 'explanation', 'note', 'citation', 'reference'];
const DEGREES: Degree[] = ['high', 'medium', 'low', 'general'];
const COMPONENTS: ComponentKind[] = ['whole', 'text', 'image', 'chart', 'layout', 'concept', 'element'];

/** The targetable elements in a slide's markup (ingest gives them `data-lectern-id`). */
export const elementsOf = (html: string | null) =>
  [...(html ?? '').matchAll(/<(\w+)[^>]*\sdata-lectern-id="([^"]+)"/g)].map((m) => ({ tag: m[1], id: m[2] }));

type Form = InfluenceIn;
type SetForm = (patch: Partial<Form>) => void;

const blank = (current: number): Form => ({
  scope: { kind: 'slide', slides: [current] },
  target: { component: 'whole', element_id: null },
  kind: 'reasoning', degree: 'medium', title: '', body: '', refs: [],
  author: { type: 'human', name: 'author' },
});

function ScopeField({ form, set, current, slides }: { form: Form; set: SetForm; current: number; slides: { n: number }[] }) {
  const { kind, slides: chosen } = form.scope;
  const pick = (k: Form['scope']['kind']) => set({ scope: { kind: k, slides: k === 'deck' ? [] : k === 'slide' ? [current] : chosen } });
  const toggle = (n: number) =>
    set({ scope: { kind, slides: chosen.includes(n) ? chosen.filter((x) => x !== n) : [...chosen, n].sort((a, b) => a - b) } });
  return (
    <fieldset>
      <legend>Shapes</legend>
      {(['slide', 'slides', 'deck'] as const).map((k) => (
        <label key={k}>
          <input type="radio" name="scope" checked={kind === k} onChange={() => pick(k)} />
          {k === 'slide' ? `this slide (${current})` : k === 'slides' ? 'choose slides' : 'whole deck'}
        </label>
      ))}
      {kind === 'slides' && (
        <div className="slide-picks">
          {slides.map((s) => (
            <label key={s.n}>
              <input type="checkbox" aria-label={`Slide ${s.n}`} checked={chosen.includes(s.n)} onChange={() => toggle(s.n)} />
              {s.n}
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

function TargetField({ form, set, elements, onPick }: { form: Form; set: SetForm; elements: { id: string }[]; onPick: () => void }) {
  const { component, element_id } = form.target;
  return (
    <>
      <label>
        Part of the slide
        <select aria-label="Component" value={component} onChange={(e) => set({ target: { component: e.target.value as ComponentKind, element_id } })}>
          {COMPONENTS.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      {component !== 'whole' && (
        <label>
          Element
          <select aria-label="Element" value={element_id ?? ''} onChange={(e) => set({ target: { component, element_id: e.target.value || null } })}>
            <option value="">(none)</option>
            {elements.map((el) => <option key={el.id} value={el.id}>{el.id}</option>)}
          </select>
          <button type="button" onClick={onPick}>Pick on slide</button>
        </label>
      )}
    </>
  );
}

function RefsField({ deckId, refs, set }: { deckId: number; refs: Ref[]; set: SetForm }) {
  const [url, setUrl] = useState('');
  const [files, setFiles] = useState<StoredFile[]>([]);
  useEffect(() => {
    void api.deckFiles(deckId).then((all) => setFiles(all.filter((f) => f.role === 'reference')), () => setFiles([]));
  }, [deckId]);
  const label = (r: Ref) => r.label ?? r.url ?? files.find((f) => f.id === r.file_id)?.path.split('/').pop() ?? r.file_id;
  const attach = async (file: File | undefined) => {
    if (!file) return;
    const stored = await api.uploadReference(deckId, file);
    setFiles((f) => [...f, stored]);
    set({ refs: [...refs, { type: 'file', file_id: stored.id, label: file.name }] });
  };
  return (
    <fieldset>
      <legend>References</legend>
      <ul>
        {refs.map((r, i) => (
          <li key={i}>
            {label(r)} <button type="button" aria-label="Remove reference" onClick={() => set({ refs: refs.filter((_, j) => j !== i) })}>×</button>
          </li>
        ))}
      </ul>
      <input aria-label="Reference URL" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
      <button type="button" disabled={!url} onClick={() => { set({ refs: [...refs, { type: 'url', url }] }); setUrl(''); }}>Add link</button>
      <input aria-label="Upload reference" type="file" accept="image/*,.pdf,.txt,.md" onChange={(e) => void attach(e.target.files?.[0])} />
      <select aria-label="Existing file" value="" onChange={(e) => e.target.value && set({ refs: [...refs, { type: 'file', file_id: e.target.value }] })}>
        <option value="">Pick an uploaded file…</option>
        {files.map((f) => <option key={f.id} value={f.id}>{f.path}</option>)}
      </select>
    </fieldset>
  );
}

interface Props {
  deckId: number;
  slides: { n: number }[];
  current: number;
  elements: { id: string }[];
  picked: string | null;
  onPick: () => void;
  existing?: Influence | null;
  onClose: () => void;
  onSaved: () => void;
}

/** "+ New influence": the same record the REST API and the MCP tools write. */
export function InfluenceDrawer({ deckId, slides, current, elements, picked, onPick, existing, onClose, onSaved }: Props) {
  const [form, setForm] = useState<Form>(existing ?? blank(current));
  const [error, setError] = useState<string | null>(null);
  const set: SetForm = (patch) => setForm((f) => ({ ...f, ...patch }));
  useEffect(() => {
    if (picked) setForm((f) => ({ ...f, target: { component: 'element', element_id: picked } }));
  }, [picked]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const { scope, target, kind, degree, title, body, refs, author } = form;
    const data = { scope, target, kind, degree, title, body, refs, author };
    try {
      await (existing ? api.updateInfluence(deckId, existing.id, data) : api.addInfluence(deckId, data));
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <aside className="drawer" role="dialog" aria-label={existing ? 'Edit influence' : 'New influence'}>
      <form onSubmit={save}>
        <h2>{existing ? 'Edit influence' : 'New influence'}</h2>
        <ScopeField form={form} set={set} current={current} slides={slides} />
        <TargetField form={form} set={set} elements={elements} onPick={onPick} />
        <label>
          Kind
          <select aria-label="Kind" value={form.kind} onChange={(e) => set({ kind: e.target.value as InfluenceKind })}>
            {KINDS.map((k) => <option key={k}>{k}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>Degree</legend>
          {DEGREES.map((d) => (
            <label key={d}>
              <input type="radio" name="degree" checked={form.degree === d} onChange={() => set({ degree: d })} />
              {d}
            </label>
          ))}
        </fieldset>
        <input aria-label="Title" placeholder="Title" required value={form.title} onChange={(e) => set({ title: e.target.value })} />
        <textarea aria-label="Explanation" placeholder="Idea, reasoning or note" value={form.body} onChange={(e) => set({ body: e.target.value })} />
        <RefsField deckId={deckId} refs={form.refs} set={set} />
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit">Save</button>
          <button type="button" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </aside>
  );
}
