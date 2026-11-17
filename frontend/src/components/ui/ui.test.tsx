import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';
import { ConfirmButton } from './ConfirmButton';
import { DataTable } from './DataTable';
import { Modal } from './Overlay';
import { SectionTabs } from './SectionTabs';
import { ToastProvider, useToast } from './Toast';

function ModalDemo() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open</Button>
      {open && (
        <Modal title="Hello" onClose={() => setOpen(false)} footer={<Button>Last</Button>}>
          <input aria-label="First field" data-autofocus />
        </Modal>
      )}
    </>
  );
}

describe('Modal', () => {
  it('moves focus in, traps Tab, closes on Esc, locks scrolling and gives focus back', () => {
    render(<ModalDemo />);
    const opener = screen.getByRole('button', { name: 'Open' });
    opener.focus();
    fireEvent.click(opener);
    expect(document.activeElement).toBe(screen.getByLabelText('First field'));
    expect(document.body.style.overflow).toBe('hidden');
    screen.getByRole('button', { name: 'Last' }).focus();
    fireEvent.keyDown(document.activeElement!, { key: 'Tab' });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }));
    fireEvent.keyDown(document.activeElement!, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Last' }));
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.body.style.overflow).toBe('');
    expect(document.activeElement).toBe(opener);
  });
});

describe('ConfirmButton', () => {
  it('stays busy until the promise settles and shows a failure', async () => {
    let fail!: (e: Error) => void;
    const onConfirm = vi.fn(() => new Promise((_, reject) => (fail = reject)));
    render(<ConfirmButton title="Delete it?" confirmLabel="Delete" onConfirm={onConfirm}>Delete</ConfirmButton>);
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const confirm = screen.getAllByRole('button', { name: 'Delete' })[1];
    await act(async () => fireEvent.click(confirm));
    expect(confirm.getAttribute('aria-busy')).toBe('true');
    await act(async () => fail(new Error('nope')));
    expect(screen.getByRole('alert').textContent).toBe('nope');
    expect(screen.getByRole('dialog', { name: 'Delete it?' })).toBeTruthy();
  });
});

describe('DataTable', () => {
  const columns = [{ key: 'name', header: 'Name', cell: (r: { name: string }) => r.name }];
  it('shows loading, rows, search and an empty state', () => {
    const { rerender } = render(<DataTable label="People" columns={columns} rows={null} rowKey={(r) => r.name} search={(r) => r.name} />);
    expect(screen.getByText('Loading…')).toBeTruthy();
    rerender(<DataTable label="People" columns={columns} rows={[{ name: 'Ada' }, { name: 'Bob' }]} rowKey={(r) => r.name} search={(r) => r.name} />);
    expect(screen.getAllByRole('row')).toHaveLength(3);
    fireEvent.change(screen.getByPlaceholderText('Search'), { target: { value: 'ad' } });
    expect(screen.getAllByRole('row')).toHaveLength(2);
    fireEvent.change(screen.getByPlaceholderText('Search'), { target: { value: 'zed' } });
    expect(screen.getByText('No matches')).toBeTruthy();
  });
});

describe('SectionTabs and Toast', () => {
  it('moves between tabs with the arrow keys', () => {
    const onChange = vi.fn();
    render(<SectionTabs label="Tabs" value="a" onChange={onChange} tabs={[{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }]} />);
    fireEvent.keyDown(screen.getByRole('tab', { name: 'A' }), { key: 'ArrowRight' });
    expect(onChange).toHaveBeenCalledWith('b');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'A' }), { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenLastCalledWith('b');
  });

  it('shows a toast for four seconds', () => {
    vi.useFakeTimers();
    function Show() {
      const { show } = useToast();
      return <Button onClick={() => show('Saved')}>Go</Button>;
    }
    render(<ToastProvider><Show /></ToastProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(screen.getByRole('status').textContent).toBe('Saved');
    act(() => vi.advanceTimersByTime(4000));
    expect(screen.getByRole('status').textContent).toBe('');
    vi.useRealTimers();
  });
});
