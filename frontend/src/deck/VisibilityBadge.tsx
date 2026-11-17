import { Globe, KeyRound, Lock } from 'lucide-react';
import type { Visibility } from '../api';
import { StatusBadge } from '../components/ui/StatusBadge';

const LOOK = {
  private: { tone: 'neutral', icon: Lock, label: 'private' },
  public: { tone: 'success', icon: Globe, label: 'public' },
  password: { tone: 'warning', icon: KeyRound, label: 'password' },
} as const;

/** Who can see a deck: private, public, or public behind a password. */
export function VisibilityBadge({ visibility }: { visibility?: Visibility | null }) {
  const { tone, icon: Icon, label } = LOOK[visibility ?? 'private'] ?? LOOK.private;
  return (
    <StatusBadge tone={tone}>
      <Icon className="h-3 w-3" aria-hidden /> {label}
    </StatusBadge>
  );
}
