import { useState } from 'react';
import { api, type Deck, type Slide, type SlideChange } from '../api';
import { useToast } from '../components/ui/Toast';
import type { EditSlide } from './SlideEdits';

/** What the slide editor drawer is doing: editing slide `n`, or making a new slide after `after`. */
export type EditorState = { mode: 'edit'; slide: Slide } | { mode: 'insert'; after: number } | null;

interface Deps {
  deck: Deck;
  setDeck: (deck: Deck) => void;
  /** Open slide `n`; `total` is the new slide count when the deck just changed. */
  go: (n: number, total?: number) => void;
  editSlide: EditSlide;
  /** Called after any change that renumbers slides (a selection by number would be stale). */
  onRenumber: () => void;
}

/**
 * The slide rail's menu actions. Each one updates the deck from the server's answer and opens the
 * slide the person will want next: the copy, the new slide, the moved slide, or the one before a
 * deleted slide.
 */
export function useSlideActions({ deck, setDeck, go, editSlide, onRenumber }: Deps) {
  const [editor, setEditor] = useState<EditorState>(null);
  const [deleting, setDeleting] = useState<Slide | null>(null);
  const { show } = useToast();
  const land = (next: Deck, n: number, message: string) => {
    setDeck(next);
    onRenumber();
    go(n, next.slides.length);
    show(message);
  };
  const run = (work: () => Promise<void>) => work().catch((e: Error) => show(e.message, 'danger'));
  return {
    editor,
    deleting,
    edit: (slide: Slide) => setEditor({ mode: 'edit', slide }),
    insertAfter: (n: number) => setEditor({ mode: 'insert', after: n }),
    askDelete: setDeleting,
    closeEditor: () => setEditor(null),
    closeDelete: () => setDeleting(null),
    duplicate: (n: number) => run(async () => {
      await api.duplicateSlide(deck.id, n);
      land(await api.getDeck(deck.id), n + 1, `Slide ${n} duplicated`);
    }),
    move: (n: number, to: number) => run(async () => land(await api.moveSlide(deck.id, n, to), to, `Slide moved to ${to}`)),
    /** Delete slide `n`; errors reach the confirm dialog. */
    remove: async (n: number) => land(await api.deleteSlide(deck.id, n), Math.max(n - 1, 1), `Slide ${n} deleted`),
    /** Save the editor: changes to an existing slide, or a new slide after `after`. */
    save: async (change: SlideChange) => {
      if (editor?.mode === 'edit') {
        await editSlide(editor.slide.n, change);
        show('Slide saved');
      } else if (editor?.mode === 'insert') {
        await api.addSlide(deck.id, { ...change, at: editor.after + 1 });
        land(await api.getDeck(deck.id), editor.after + 1, 'Slide added');
      }
    },
  };
}

export type SlideActions = ReturnType<typeof useSlideActions>;
