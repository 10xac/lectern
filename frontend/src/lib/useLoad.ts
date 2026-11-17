import { useCallback, useEffect, useState } from 'react';

/**
 * Load something when the page opens (and again on `reload`). `data` is null until it arrives;
 * `error` holds the message of a failed load. `load` must be stable (e.g. a module function).
 */
export function useLoad<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    load().then(
      (d) => live && (setData(d), setError(null)),
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
  }, [load, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, reload, setData };
}
