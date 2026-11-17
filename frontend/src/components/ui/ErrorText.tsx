import { AlertCircle } from 'lucide-react';

/** An error message, announced to screen readers. Renders nothing without one. */
export function ErrorText({ children }: { children?: string | null }) {
  if (!children) return null;
  return (
    <p role="alert" className="flex items-start gap-1.5 text-sm text-danger-ink">
      <AlertCircle className="mt-[3px] h-4 w-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
