import { Upload } from 'lucide-react';
import { useId, useState, type ChangeEvent } from 'react';
import { cn } from '../lib/cn';
import { buttonStyles, type ButtonVariants } from './ui/styles';
import { useToast } from './ui/Toast';

interface Props<T> extends ButtonVariants {
  label: string;
  accept: string;
  upload: (file: File) => Promise<T>;
  onDone: (result: T) => void;
}

/** A button that picks a file and uploads it at once. Errors appear as a toast. */
export function UploadButton<T>({ label, accept, upload, onDone, variant, size }: Props<T>) {
  const [busy, setBusy] = useState(false);
  const { show } = useToast();
  const id = useId();
  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    try {
      onDone(await upload(file));
      show(`${file.name} uploaded`);
    } catch (err) {
      show((err as Error).message, 'danger');
    } finally {
      setBusy(false);
    }
  };
  return (
    <span>
      <input id={id} type="file" className="peer sr-only" accept={accept} disabled={busy} onChange={(e) => void choose(e)} aria-label={label} />
      <label htmlFor={id} className={cn(buttonStyles({ variant, size }), 'cursor-pointer peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-brand/60', busy && 'opacity-60')}>
        <Upload className="h-4 w-4" aria-hidden /> {busy ? 'Uploading…' : label}
      </label>
    </span>
  );
}
