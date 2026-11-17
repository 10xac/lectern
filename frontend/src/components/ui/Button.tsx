import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';
import { buttonStyles, type ButtonVariants } from './styles';

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & ButtonVariants & { busy?: boolean };

/** A button from the design system; `busy` disables it and shows a spinner. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, busy, className, children, disabled, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(buttonStyles({ variant, size }), className)}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy && <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />}
      {children}
    </button>
  );
});
