import { useState, type ReactNode } from 'react';
import { Button, type ButtonProps } from './Button';
import { ErrorText } from './ErrorText';
import { Modal } from './Overlay';

interface DialogProps {
  /** The dialog's title, e.g. "Disable ada@example.org?" */
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}

/** Ask before something destructive. The confirm button stays busy until `onConfirm` settles. */
export function ConfirmDialog({ title, description, confirmLabel = 'Confirm', onConfirm, onClose }: DialogProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title={title}
      onClose={() => !busy && onClose()}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" className="bg-danger hover:bg-danger/90 active:bg-danger-ink" busy={busy} onClick={() => void confirm()}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {description && <div className="text-sm text-ink-soft">{description}</div>}
      <ErrorText>{error}</ErrorText>
    </Modal>
  );
}

type Props = Omit<ButtonProps, 'onClick' | 'title'> & Omit<DialogProps, 'onClose'>;

/** A button that asks first (see ConfirmDialog). */
export function ConfirmButton({ title, description, confirmLabel, onConfirm, children, ...rest }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button {...rest} onClick={() => setOpen(true)}>
        {children}
      </Button>
      {open && <ConfirmDialog title={title} description={description} confirmLabel={confirmLabel} onConfirm={onConfirm} onClose={() => setOpen(false)} />}
    </>
  );
}
