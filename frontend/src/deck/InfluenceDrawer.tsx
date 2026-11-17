import { MousePointerClick } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { api, type Degree, type Influence, type InfluenceKind } from '../api';
import { Button } from '../components/ui/Button';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input, TextArea } from '../components/ui/Field';
import { Drawer } from '../components/ui/Overlay';
import { useToast } from '../components/ui/Toast';
import { Pills, RefsField, ScopeField, TargetField, type Form, type SetForm } from './InfluenceFields';

const KINDS: InfluenceKind[] = ['idea', 'reasoning', 'explanation', 'note', 'citation', 'reference'];
const DEGREES: Degree[] = ['high', 'medium', 'low', 'general'];

/** The targetable elements in a slide's markup (ingest gives them `data-lectern-id`). */
export const elementsOf = (html: string | null) =>
  [...(html ?? '').matchAll(/<(\w+)[^>]*\sdata-lectern-id="([^"]+)"/g)].map((m) => ({ tag: m[1], id: m[2] }));

const blank = (current: number, slides?: number[]): Form => ({
  scope: slides && slides.length > 1 ? { kind: 'slides', slides } : { kind: 'slide', slides: [slides?.[0] ?? current] },
  target: { component: 'whole', element_id: null },
  kind: 'reasoning', degree: 'medium', title: '', body: '', refs: [],
  author: { type: 'human', name: 'author' },
});

interface Props {
  deckId: number;
  slides: { n: number }[];
  current: number;
  /** For a new influence: the selected slides it starts scoped to. */
  scoped?: number[];
  elements: { id: string }[];
  picking: boolean;
  picked: string | null;
  onPick: () => void;
  onStopPicking: () => void;
  existing?: Influence | null;
  readOnly?: boolean;
  author?: string;
  onClose: () => void;
  onSaved: () => void;
}

/** "+ Influence": the same record the REST API and the MCP tools write. Read-only for visitors. */
export function InfluenceDrawer(props: Props) {
  const { deckId, existing, readOnly, onClose, onSaved, picking, picked } = props;
  const [form, setForm] = useState<Form>(() => existing ?? { ...blank(props.current, props.scoped), author: { type: 'human', name: props.author ?? 'author' } });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { show } = useToast();
  const set: SetForm = (patch) => setForm((f) => ({ ...f, ...patch }));
  useEffect(() => {
    if (picked) setForm((f) => ({ ...f, target: { component: 'element', element_id: picked } }));
  }, [picked]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const { scope, target, kind, degree, title, body, refs, author } = form;
    const data = { scope, target, kind, degree, title, body, refs, author };
    setBusy(true);
    try {
      await (existing ? api.updateInfluence(deckId, existing.id, data) : api.addInfluence(deckId, data));
      show(existing ? 'Influence saved' : 'Influence added');
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  // While picking, the drawer steps aside (keeping the form) so the slide can be clicked.
  if (picking) return <PickBanner onCancel={props.onStopPicking} />;
  const title = readOnly ? 'Influence' : existing ? 'Edit influence' : 'New influence';
  const footer = readOnly ? <Button onClick={onClose}>Close</Button> : (
    <><Button onClick={onClose}>Cancel</Button><Button type="submit" form="influence-form" variant="primary" busy={busy}>Save</Button></>
  );
  return (
    <Drawer title={title} onClose={onClose} footer={footer} size="lg">
      <form id="influence-form" onSubmit={save}>
        <fieldset disabled={readOnly} className="min-w-0">
          <ScopeField form={form} set={set} current={props.current} slides={props.slides} />
          <TargetField form={form} set={set} elements={props.elements} onPick={props.onPick} />
          <Pills legend="Kind" name="kind" value={form.kind} onChange={(kind) => set({ kind })} options={KINDS.map((k) => [k, k])} />
          <Pills legend="Degree" name="degree" value={form.degree} onChange={(degree) => set({ degree })} options={DEGREES.map((d) => [d, d])} />
          <Field label="Title">{(id) => <Input id={id} required value={form.title} onChange={(e) => set({ title: e.target.value })} />}</Field>
          <Field label="Explanation">{(id) => <TextArea id={id} rows={5} placeholder="The idea, reasoning or note" value={form.body} onChange={(e) => set({ body: e.target.value })} />}</Field>
          <RefsField deckId={deckId} refs={form.refs} set={set} />
        </fieldset>
        <ErrorText>{error}</ErrorText>
      </form>
    </Drawer>
  );
}

function PickBanner({ onCancel }: { onCancel: () => void }) {
  return (
    <div role="status" className="fixed inset-x-0 top-20 z-50 mx-auto flex w-fit max-w-[90vw] items-center gap-3 rounded-lg bg-ink-strong px-4 py-2.5 text-sm text-white shadow-card">
      <MousePointerClick className="h-4 w-4" aria-hidden />
      Click an outlined element on the slide.
      <Button size="sm" variant="ghost" className="text-white hover:bg-white/10 hover:text-white" onClick={onCancel}>Cancel</Button>
    </div>
  );
}
