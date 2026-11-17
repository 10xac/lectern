import { Plus } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Button } from './Button';
import { Card } from './Card';

interface Props {
  /** "New token", "Invite user"… the button label and the card's title. */
  label: string;
  /** The form; call `close` when done. */
  children: (close: () => void) => ReactNode;
}

/** A "New X" button that reveals a form card in place. */
export function CreatePanel({ label, children }: Props) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <Button variant="primary" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" aria-hidden /> {label}
      </Button>
    );
  }
  return (
    <Card title={label} className="w-full shadow-card" actions={<Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>}>
      {children(() => setOpen(false))}
    </Card>
  );
}
