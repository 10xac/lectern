import { Copy } from 'lucide-react';
import type { ReactNode } from 'react';
import { copyText } from '../../lib/format';
import { Button } from './Button';
import { useToast } from './Toast';

/** A value to copy now (an invite link, a token): warning-tinted, monospace, with a Copy button. */
export function SecretBox({ value, label, children }: { value: string; label: string; children?: ReactNode }) {
  const { show } = useToast();
  const copy = async () => { const ok = await copyText(value); show(ok ? 'Copied' : 'Copy failed: select the text instead', ok ? 'success' : 'danger'); };
  return (
    <div role="status" aria-label={label} className="rounded-lg border border-warning-line bg-warning-soft p-4">
      {children && <div className="mb-2 text-sm text-warning-ink">{children}</div>}
      <div className="flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all rounded border border-warning-line bg-surface px-2 py-1 font-mono text-xs leading-5">{value}</code>
        <Button size="sm" onClick={() => void copy()} aria-label={`Copy ${label}`}>
          <Copy className="h-3.5 w-3.5" aria-hidden /> Copy
        </Button>
      </div>
    </div>
  );
}

/** A command or URL to paste somewhere, monospace, with its own Copy button. */
export function CodeLine({ value, label }: { value: string; label: string }) {
  const { show } = useToast();
  return (
    <div className="flex items-start gap-2 rounded bg-surface-sunken p-2">
      <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5 text-ink">{value}</code>
      <Button size="sm" variant="ghost" aria-label={`Copy ${label}`} onClick={() => void copyText(value).then((ok) => show(ok ? 'Copied' : 'Copy failed', ok ? 'success' : 'danger'))}>
        <Copy className="h-3.5 w-3.5" aria-hidden />
      </Button>
    </div>
  );
}
