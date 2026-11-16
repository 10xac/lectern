import { useState, type ChangeEvent } from 'react';

interface Props<T> {
  label: string;
  accept: string;
  upload: (file: File) => Promise<T>;
  onDone: (result: T) => void;
}

/** A file picker that uploads as soon as a file is chosen. Used for decks and for author data. */
export function Upload<T>({ label, accept, upload, onDone }: Props<T>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await upload(file));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="upload">
      <label>
        {busy ? 'Uploading…' : label}
        <input type="file" accept={accept} disabled={busy} onChange={choose} />
      </label>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
