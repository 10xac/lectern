import { useState, type ReactNode } from 'react';
import type { ModelSettings } from '../api';
import { Button } from '../components/ui/Button';
import { ConfirmButton } from '../components/ui/ConfirmButton';
import { Input, Select } from '../components/ui/Field';
import { StatusBadge } from '../components/ui/StatusBadge';

type Save = (name: string, value: string | null) => Promise<void>;
type Setting = ModelSettings['settings'][number];
type Key = ModelSettings['keys'][number];

function Row({ name, source, children }: { name: string; source: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-2 border-b border-line-soft py-3 last:border-0 md:grid-cols-[220px_1fr] md:items-center">
      <div>
        <div className="font-mono text-xs text-ink-strong">{name}</div>
        <div className="text-xs text-ink-muted">{source}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

/** One plain setting: a text box (or a select), saved with its own button. Empty clears it. */
export function SettingRow({ setting, choices, save }: { setting: Setting; choices?: string[]; save: Save }) {
  const [value, setValue] = useState(setting.value);
  const [busy, setBusy] = useState(false);
  const changed = value !== setting.value;
  const submit = async () => {
    setBusy(true);
    await save(setting.name, value || null).catch(() => undefined);
    setBusy(false);
  };
  return (
    <Row name={setting.name} source={setting.source === 'unset' ? 'not set' : `from ${setting.source}`}>
      {choices ? (
        <Select aria-label={setting.name} className="min-w-0 flex-1" value={value} onChange={(e) => setValue(e.target.value)}>
          {[...new Set([...choices, value])].map((c) => <option key={c} value={c}>{c || '(automatic)'}</option>)}
        </Select>
      ) : (
        <Input aria-label={setting.name} className="min-w-0 flex-1" value={value} onChange={(e) => setValue(e.target.value)} />
      )}
      <Button size="md" disabled={!changed} busy={busy} onClick={() => void submit()}>Save</Button>
    </Row>
  );
}

/** One API key: never shown; "configured ••••1234 (source)" or "not set"; rotate or remove. */
export function KeyRow({ item, canStore, save }: { item: Key; canStore: boolean; save: Save }) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    await save(item.name, value).then(() => setValue(''), () => undefined);
    setBusy(false);
  };
  const status = item.set
    ? <StatusBadge tone="success">configured ••••{item.last4 ?? ''} ({item.source})</StatusBadge>
    : <StatusBadge>not set</StatusBadge>;
  return (
    <Row name={item.name} source={status}>
      <Input aria-label={`New value for ${item.name}`} type="password" autoComplete="off" className="min-w-0 flex-1" placeholder={item.set ? 'New value to rotate' : 'Paste a key'}
        disabled={!canStore} value={value} onChange={(e) => setValue(e.target.value)} />
      <Button disabled={!value} busy={busy} onClick={() => void submit()}>Save</Button>
      {item.source === 'lectern' && (
        <ConfirmButton variant="danger" title={`Remove ${item.name}?`} confirmLabel="Remove" description="The key stored in lectern is deleted. A key in the server's environment, if any, applies again." onConfirm={() => save(item.name, null)}>
          Remove
        </ConfirmButton>
      )}
    </Row>
  );
}
