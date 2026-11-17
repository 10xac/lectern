/** A unix time (seconds) as a short date, or a dash. */
export const day = (t: number | null | undefined) =>
  t ? new Date(t * 1000).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '—';

/** The initials of an email address, for the avatar: "ada.lovelace@x" → "AL". */
export function initials(email: string | null | undefined): string {
  const name = (email ?? '').split('@')[0];
  const parts = name.split(/[._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return (letters || '?').toUpperCase();
}

/** Copy text; resolves false when the browser refuses (insecure origin, permissions). */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
