import { Link2, MousePointerClick, Paperclip, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, type ComponentKind, type InfluenceIn, type Ref, type StoredFile } from '../api';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Field';
import { cn } from '../lib/cn';

export type Form = InfluenceIn;
export type SetForm = (patch: Partial<Form>) => void;
const COMPONENTS: ComponentKind[] = ['whole', 'text', 'image', 'chart', 'layout', 'concept', 'element'];

/** Radio buttons drawn as a row of pills; still real radios for keyboards and screen readers. */
export function Pills<T extends string>({ legend, name, value, options, onChange }: {
  legend: string; name: string; value: T; options: [T, string][]; onChange: (v: T) => void;
}) {
  return (
    <fieldset className="mb-4">
      <legend className="mb-1 text-sm text-ink-strong">{legend}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map(([v, label]) => (
          <label key={v} className={cn('cursor-pointer rounded border px-3 py-1 text-sm has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand/60',
            value === v ? 'border-brand bg-brand-soft text-brand-strong' : 'border-line text-ink hover:border-brand-hover')}>
            <input type="radio" className="sr-only" name={name} checked={value === v} onChange={() => onChange(v)} />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function ScopeField({ form, set, current, slides }: { form: Form; set: SetForm; current: number; slides: { n: number }[] }) {
  const { kind, slides: chosen } = form.scope;
  const pick = (k: Form['scope']['kind']) => set({ scope: { kind: k, slides: k === 'deck' ? [] : k === 'slide' ? [current] : chosen } });
  const toggle = (n: number) =>
    set({ scope: { kind, slides: chosen.includes(n) ? chosen.filter((x) => x !== n) : [...chosen, n].sort((a, b) => a - b) } });
  return (
    <>
      <Pills legend="Shapes" name="scope" value={kind} onChange={pick}
        options={[['slide', `This slide (${current})`], ['slides', 'Chosen slides'], ['deck', 'Whole deck']]} />
      {kind === 'slides' && (
        <fieldset className="-mt-2 mb-4 flex flex-wrap gap-1.5">
          <legend className="sr-only">Slides</legend>
          {slides.map((s) => (
            <label key={s.n} className={cn('flex h-8 w-10 cursor-pointer items-center justify-center rounded border text-sm', chosen.includes(s.n) ? 'border-brand bg-brand text-white' : 'border-line')}>
              <input type="checkbox" className="sr-only" aria-label={`Slide ${s.n}`} checked={chosen.includes(s.n)} onChange={() => toggle(s.n)} />
              {s.n}
            </label>
          ))}
        </fieldset>
      )}
    </>
  );
}

export function TargetField({ form, set, elements, onPick }: { form: Form; set: SetForm; elements: { id: string }[]; onPick: () => void }) {
  const { component, element_id } = form.target;
  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-2">
      <label className="block text-sm text-ink-strong">
        Part of the slide
        <Select aria-label="Component" className="mt-1" value={component} onChange={(e) => set({ target: { component: e.target.value as ComponentKind, element_id } })}>
          {COMPONENTS.map((c) => <option key={c}>{c}</option>)}
        </Select>
      </label>
      {component !== 'whole' && (
        <div className="text-sm text-ink-strong">
          <label htmlFor="influence-element">Element</label>
          <div className="mt-1 flex gap-1">
            <Select id="influence-element" aria-label="Element" value={element_id ?? ''} onChange={(e) => set({ target: { component, element_id: e.target.value || null } })}>
              <option value="">(none)</option>
              {elements.map((el) => <option key={el.id} value={el.id}>{el.id}</option>)}
              {element_id && !elements.some((el) => el.id === element_id) && <option value={element_id}>{element_id}</option>}
            </Select>
            <Button onClick={onPick} aria-label="Pick on slide" title="Pick on slide"><MousePointerClick className="h-4 w-4" aria-hidden /></Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function RefsField({ deckId, refs, set }: { deckId: number; refs: Ref[]; set: SetForm }) {
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
    <fieldset className="mb-4">
      <legend className="mb-1 text-sm text-ink-strong">References</legend>
      {refs.length > 0 && (
        <ul className="mb-2 space-y-1">
          {refs.map((r, i) => (
            <li key={i} className="flex items-center gap-2 rounded bg-surface-sunken px-2 py-1 text-sm">
              {r.type === 'url' ? <Link2 className="h-3.5 w-3.5 text-ink-muted" aria-hidden /> : <Paperclip className="h-3.5 w-3.5 text-ink-muted" aria-hidden />}
              <span className="min-w-0 flex-1 truncate">{label(r)}</span>
              <Button variant="ghost" size="icon" className="h-6 w-6" aria-label="Remove reference" onClick={() => set({ refs: refs.filter((_, j) => j !== i) })}><X className="h-3.5 w-3.5" aria-hidden /></Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input aria-label="Reference URL" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
        <Button disabled={!url} onClick={() => { set({ refs: [...refs, { type: 'url', url }] }); setUrl(''); }}>Add link</Button>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <label className="flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded border border-dashed border-line text-sm text-ink-soft hover:border-brand hover:text-brand has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand/60">
          <Paperclip className="h-3.5 w-3.5" aria-hidden /> Upload a file
          <input aria-label="Upload reference" type="file" className="sr-only" accept="image/*,.pdf,.txt,.md" onChange={(e) => void attach(e.target.files?.[0])} />
        </label>
        <Select aria-label="Existing file" value="" onChange={(e) => e.target.value && set({ refs: [...refs, { type: 'file', file_id: e.target.value }] })}>
          <option value="">Pick an uploaded file…</option>
          {files.map((f) => <option key={f.id} value={f.id}>{f.path}</option>)}
        </Select>
      </div>
    </fieldset>
  );
}
