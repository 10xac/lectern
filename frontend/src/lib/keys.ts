/** True when a key press belongs to something else: a form field, an open dialog or a menu. */
export function keyIsTaken(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement | null;
  if (e.altKey || e.ctrlKey || e.metaKey) return true;
  if (!t || typeof t.closest !== 'function') return false;
  return Boolean(t.closest('input, textarea, select, [contenteditable="true"], [role="dialog"], [role="menu"], [role="tablist"]'));
}
