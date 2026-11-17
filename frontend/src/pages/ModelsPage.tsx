import { useCallback, useState } from 'react';
import { api, type ModelSettings } from '../api';
import { Card } from '../components/ui/Card';
import { ErrorText } from '../components/ui/ErrorText';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useToast } from '../components/ui/Toast';
import { Page } from '../layout/AppShell';
import { useLoad } from '../lib/useLoad';
import { KeyRow, SettingRow } from './ModelRows';

const MAIN = ['LECTERN_PROVIDER', 'LECTERN_MODEL', 'LECTERN_BASE_URL', 'LECTERN_MODEL_ALLOWLIST'];
const TRIAGE = ['SYSTEM1_MODEL_PROVIDER', 'SYSTEM1_MODEL_NAME', 'SYSTEM1_BASE_URL', 'LECTERN_JEV_MODEL'];
export const CHOICES: Record<string, string[]> = {
  LECTERN_PROVIDER: ['fake', 'anthropic', 'openai_compat'],
  SYSTEM1_MODEL_PROVIDER: ['', 'openrouter', 'openai', 'google', 'anthropic', 'openai_compat'],
};

/** Admins choose the main model, the triage model (System1) and the API keys (write-only). */
export function ModelsPage() {
  const { data, error, setData } = useLoad(api.modelSettings);
  const { show } = useToast();
  const [failed, setFailed] = useState<string | null>(null);
  const save = useCallback(async (name: string, value: string | null) => {
    try {
      setData(await api.putSetting(name, value));
      setFailed(null);
      show(value === null ? `${name} cleared` : `${name} saved`);
    } catch (e) {
      setFailed((e as Error).message);
      throw e;
    }
  }, [setData, show]);
  return (
    <Page>
      <PageHeader title="Models & keys" crumbs={[{ label: 'Platform' }, { label: 'Models & keys' }]} description="What answers questions, what triages them, and the keys they use. Values saved here take precedence over the server's environment." />
      <ErrorText>{error ?? failed}</ErrorText>
      {data && <Settings data={data} save={save} />}
    </Page>
  );
}

function Settings({ data, save }: { data: ModelSettings; save: (name: string, value: string | null) => Promise<void> }) {
  const rows = (names: string[]) =>
    names.map((n) => data.settings.find((s) => s.name === n)).filter((s) => s !== undefined)
      .map((s) => <SettingRow key={s.name} setting={s} choices={CHOICES[s.name]} save={save} />);
  const s1 = data.system1;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title="Main model">{rows(MAIN)}</Card>
      <Card title="Triage (System1)">
        <div className="mb-4 rounded-lg bg-surface-muted p-3 text-sm" aria-label="Resolved triage">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="info">{s1.kind}</StatusBadge>
            {s1.provider && <StatusBadge>{s1.provider}</StatusBadge>}
            {s1.model && <span className="font-mono text-xs">{s1.model}</span>}
          </div>
          <p className="mt-1 text-ink-soft">{s1.why}</p>
        </div>
        {rows(TRIAGE)}
      </Card>
      <Card title="API keys" className="xl:col-span-2">
        {!data.store_configured && (
          <p className="mb-4 rounded-lg border border-info-line bg-info-soft p-3 text-sm text-ink">
            Keys cannot be stored here yet: set <code className="font-mono">LECTERN_SECRET_KEY</code> on the server to encrypt them. Keys from the environment still work.
          </p>
        )}
        {data.keys.map((k) => <KeyRow key={k.name} item={k} canStore={data.store_configured} save={save} />)}
      </Card>
    </div>
  );
}
