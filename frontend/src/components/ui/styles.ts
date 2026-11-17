// The design system's recipes. Components use these; pages may too (e.g. a link styled as a button).
import { cva, type VariantProps } from 'class-variance-authority';

export const buttonStyles = cva(
  'inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded font-normal transition-colors ' +
    'disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 ' +
    'focus-visible:outline-offset-2 focus-visible:outline-brand/60',
  {
    variants: {
      variant: {
        primary: 'bg-brand text-white shadow-sm hover:bg-brand-hover active:bg-brand-strong',
        default: 'border border-line bg-surface text-ink hover:border-brand hover:text-brand',
        ghost: 'text-ink-soft hover:bg-surface-hover hover:text-ink',
        link: 'text-brand underline-offset-2 hover:text-brand-hover hover:underline',
        danger: 'border border-danger bg-surface text-danger-ink hover:bg-danger-soft',
      },
      size: {
        sm: 'h-7 px-2 text-sm',
        md: 'h-8 px-[15px] text-sm',
        cta: 'h-10 px-6 text-base',
        icon: 'h-8 w-8 p-0',
      },
    },
    compoundVariants: [{ variant: 'link', className: 'h-auto px-0' }],
    defaultVariants: { variant: 'default', size: 'md' },
  },
);
export type ButtonVariants = VariantProps<typeof buttonStyles>;

export const inputStyles = cva(
  'w-full rounded border border-line bg-surface px-[11px] text-sm text-ink placeholder:text-ink-faint ' +
    'hover:border-brand-hover focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 ' +
    'disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-muted',
  {
    variants: {
      kind: { input: 'h-8', select: 'h-8 pr-8', textarea: 'min-h-[88px] py-1.5 leading-[1.375rem]', compact: 'min-h-10 resize-none py-2 leading-5' },
      invalid: { true: 'border-danger hover:border-danger focus:border-danger focus:ring-danger/20' },
    },
    defaultVariants: { kind: 'input' },
  },
);

export const badgeStyles = cva(
  'inline-flex items-center gap-1 whitespace-nowrap rounded border px-[7px] text-xs leading-5',
  {
    variants: {
      tone: {
        success: 'border-success-line bg-success-soft text-[#389E0D]',
        warning: 'border-warning-line bg-warning-soft text-warning-ink',
        info: 'border-info-line bg-info-soft text-info',
        danger: 'border-danger-line bg-danger-soft text-danger-ink',
        brand: 'border-brand/30 bg-brand-soft text-brand-strong',
        pink: 'border-tag-pink-line bg-tag-pink-bg text-tag-pink-fg',
        cyan: 'border-tag-cyan-line bg-tag-cyan-bg text-[#08979C]',
        orange: 'border-tag-orange-line bg-tag-orange-bg text-[#D46B08]',
        teal: 'border-tag-teal-line bg-tag-teal-bg text-tag-teal-fg',
        neutral: 'border-tag-neutral-line bg-tag-neutral-bg text-tag-neutral-fg',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);
export type Tone = NonNullable<VariantProps<typeof badgeStyles>['tone']>;

/** A small uppercase label above a group of controls. */
export const labelStyles = 'mb-1 block text-sm text-ink-strong';
