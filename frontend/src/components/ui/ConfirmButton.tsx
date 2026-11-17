import { useState, type ReactNode } from 'react';
import { Button, type ButtonProps } from './Button';
import { ErrorText } from './ErrorText';
import { Modal } from './Overlay';

interface Props extends Omit<ButtonProps, 'onClick' | 'title'> {
  /** The dialog's title, e.g. "Disable ada@example.org?" */
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  onConfirm: () => Promise<unknown>;
}

/** A button that asks first. The confirm button stays busy until `onConfirm` settles. */
export function ConfirmButton({ title, description, confirmLabel = 'Confirm', onConfirm, children, ...rest }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button {...rest} onClick={() => setOpen(true)}>
        {children}
      </Button>
      {open && (
        <Modal
          title={title}
          onClose={() => !busy && setOpen(false)}
          footer={
            <>
              <Button onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
              <Button variant="primary" className="bg-danger hover:bg-danger/90 active:bg-danger-ink" busy={busy} onClick={() => void confirm()}>
                {confirmLabel}
              </Button>
            </>
          }
        >
          {description && <div className="text-sm text-ink-soft">{description}</div>}
          <ErrorText>{error}</ErrorText>
        </Modal>
      )}
    </>
  );
}
