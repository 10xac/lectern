import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';
import { inputStyles } from './styles';

interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  className?: string;
  children: (id: string) => ReactNode;
}

/** A label above a control, with an optional hint below. */
export function Field({ label, hint, className, children }: FieldProps) {
  const id = useId();
  return (
    <div className={cn('mb-4', className)}>
      <label htmlFor={id} className="mb-1 block text-sm text-ink-strong">{label}</label>
      {children(id)}
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(inputStyles(), className)} {...rest} />;
});

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(inputStyles({ kind: 'select' }), className)} {...rest} />;
}

/** A multi-line box; `compact` starts at one line (a chat box). */
export function TextArea({ className, compact, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { compact?: boolean }) {
  return <textarea className={cn(inputStyles({ kind: compact ? 'compact' : 'textarea' }), className)} {...rest} />;
}
