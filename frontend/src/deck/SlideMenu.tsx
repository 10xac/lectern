import { ArrowDown, ArrowUp, Copy, Pencil, Plus, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '../components/ui/ConfirmButton';
import { Menu } from '../components/ui/Menu';
import type { Slide } from '../api';
import { SlideEditor } from './SlideEditor';
import type { SlideActions } from './useSlideActions';

interface Props {
  slide: Slide;
  count: number;
  actions: SlideActions;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  className?: string;
}

/** A rail thumbnail's kebab menu (also opened by right-clicking the thumbnail). */
export function SlideMenu({ slide, count, actions, open, onOpenChange, className }: Props) {
  const n = slide.n;
  return (
    <Menu label={`Actions for slide ${n}`} open={open} onOpenChange={onOpenChange} className={className} items={[
      { label: 'Edit slide…', icon: Pencil, onSelect: () => actions.edit(slide) },
      { label: 'Duplicate', icon: Copy, onSelect: () => void actions.duplicate(n) },
      { label: 'Insert slide after', icon: Plus, onSelect: () => actions.insertAfter(n) },
      { label: 'Move up', icon: ArrowUp, disabled: n <= 1, onSelect: () => void actions.move(n, n - 1) },
      { label: 'Move down', icon: ArrowDown, disabled: n >= count, onSelect: () => void actions.move(n, n + 1) },
      { label: 'Delete', icon: Trash2, danger: true, disabled: count <= 1, onSelect: () => actions.askDelete(slide) },
    ]} />
  );
}

/** The editor drawer and the delete confirmation the slide menu opens. */
export function SlideActionDialogs({ actions }: { actions: SlideActions }) {
  const { editor, deleting } = actions;
  return (
    <>
      {editor && (
        <SlideEditor key={editor.mode === 'edit' ? `edit-${editor.slide.n}` : `insert-${editor.after}`}
          slide={editor.mode === 'edit' ? editor.slide : undefined}
          title={editor.mode === 'edit' ? `Edit slide ${editor.slide.n}` : `New slide after ${editor.after}`}
          onSave={actions.save} onClose={actions.closeEditor} />
      )}
      {deleting && (
        <ConfirmDialog title={`Delete slide ${deleting.n}?`} confirmLabel="Delete slide" onConfirm={() => actions.remove(deleting.n)} onClose={actions.closeDelete}
          description={`“${deleting.title || `Slide ${deleting.n}`}” is removed and the slides after it move up one. This cannot be undone.`} />
      )}
    </>
  );
}
