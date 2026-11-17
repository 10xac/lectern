import type { ReactNode } from 'react';
import { Logo } from './Logo';

/** A neutral drawing for the sign-in pages: a slide on a stand, with chat bubbles answering it. */
function Illustration() {
  return (
    <svg viewBox="0 0 360 280" className="h-auto w-full max-w-[420px]" aria-hidden>
      <ellipse cx="180" cy="252" rx="150" ry="14" fill="#F0F0F0" />
      <rect x="40" y="40" width="210" height="130" rx="8" fill="#fff" stroke="#D9D9D9" />
      <rect x="58" y="60" width="110" height="12" rx="3" className="fill-brand" opacity=".85" />
      <rect x="58" y="84" width="160" height="7" rx="3" fill="#E5E5E5" />
      <rect x="58" y="98" width="140" height="7" rx="3" fill="#E5E5E5" />
      <rect x="58" y="120" width="44" height="34" rx="4" fill="#EEF2FF" />
      <rect x="110" y="132" width="44" height="22" rx="4" fill="#E6F4FF" />
      <rect x="162" y="112" width="44" height="42" rx="4" fill="#F6FFED" />
      <path d="M145 170v62M120 240h50" stroke="#BFBFBF" strokeWidth="6" strokeLinecap="round" />
      <rect x="226" y="120" width="104" height="40" rx="10" className="fill-brand" />
      <rect x="240" y="134" width="60" height="5" rx="2.5" fill="#fff" opacity=".9" />
      <rect x="240" y="145" width="40" height="5" rx="2.5" fill="#fff" opacity=".7" />
      <rect x="244" y="172" width="96" height="34" rx="10" fill="#fff" stroke="#D9D9D9" />
      <rect x="258" y="185" width="56" height="5" rx="2.5" fill="#BFBFBF" />
      <circle cx="300" cy="62" r="18" fill="#FFF7E6" stroke="#FFD591" />
      <path d="M292 62l6 6 10-12" fill="none" stroke="#FA8C16" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The frame of the sign-in, invite and consent pages: logo, drawing, a 320px form, footer. */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <header className="flex h-topbar items-center border-b border-line-soft px-6">
        <Logo />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="flex w-full max-w-4xl items-center justify-center gap-16">
          <div className="hidden flex-1 justify-center md:flex">
            <Illustration />
          </div>
          <div className="w-full max-w-[320px]">
            <h1 className="font-display text-2xl font-semibold text-ink-strong">{title}</h1>
            {subtitle && <div className="mb-6 mt-1 text-sm text-ink-soft">{subtitle}</div>}
            {!subtitle && <div className="mb-6" />}
            {children}
          </div>
        </div>
      </main>
      <footer className="py-6 text-center text-xs text-ink-muted">lectern ©{new Date().getFullYear()}</footer>
    </div>
  );
}
