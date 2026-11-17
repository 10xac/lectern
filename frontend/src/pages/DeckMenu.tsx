import { Pencil, Trash2 } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';
import { api, type DeckSummary } from '../api';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmButton';
import { ErrorText } from '../components/ui/ErrorText';
import { Field, Input } from '../components/ui/Field';
import { Menu } from '../components/ui/Menu';
import { Modal } from '../components/ui/Overlay';
import { useToast } from '../components/ui/Toast';

/** Rename a deck in a small dialog. */
function RenameDeck({ deck, onClose, onDone }: { deck: DeckSummary; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(deck.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { show } = useToast();
  const formId = useId();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.renameDeck(deck.id, title.trim());
      show('Deck renamed');
      onDone();
      onClose();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };
  const footer = (
    <>
      <Button onClick={onClose}>Cancel</Button>
      <Button type="submit" form={formId} variant="primary" busy={busy} disabled={!title.trim() || title.trim() === deck.title}>Rename</Button>
    </>
  );
  return (
    <Modal title="Rename deck" onClose={onClose} footer={footer}>
      <form id={formId} onSubmit={(e) => void submit(e)} aria-label="Rename deck">
        <Field label="Title">{(id) => <Input id={id} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
        <ErrorText>{error}</ErrorText>
      </form>
    </Modal>
  );
}

/** A deck card's kebab menu: rename or delete the deck; `onChanged` refreshes the list. */
export function DeckMenu({ deck, onChanged, className }: { deck: DeckSummary; onChanged: () => void; className?: string }) {
  const [dialog, setDialog] = useState<'rename' | 'delete' | null>(null);
  const { show } = useToast();
  const remove = async () => {
    await api.deleteDeck(deck.id);
    show(`Deleted ${deck.title}`);
    onChanged();
  };
  return (
    <>
      <Menu label={`Actions for ${deck.title}`} className={className} items={[
        { label: 'Rename', icon: Pencil, onSelect: () => setDialog('rename') },
        { label: 'Delete', icon: Trash2, danger: true, onSelect: () => setDialog('delete') },
      ]} />
      {dialog === 'rename' && <RenameDeck deck={deck} onClose={() => setDialog(null)} onDone={onChanged} />}
      {dialog === 'delete' && (
        <ConfirmDialog title={`Delete ${deck.title}?`} confirmLabel="Delete deck" onConfirm={remove} onClose={() => setDialog(null)}
          description="This removes the deck with all its slides, DNA, chats and files. It cannot be undone." />
      )}
    </>
  );
}
