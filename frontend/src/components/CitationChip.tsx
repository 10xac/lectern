import type { Citation } from '../api';

/** "slide:4:notes" → "slide 4 · notes", "att:2:0" → "data 2 · part 1", "deck:outline" → "outline". */
export function chipLabel(blockId: string): string {
  const [kind, a, b] = blockId.split(':');
  if (kind === 'slide') return `slide ${a} · ${b}`;
  if (kind === 'att') return `data ${a} · part ${Number(b) + 1}`;
  if (kind === 'dna') return 'DNA';
  if (kind === 'file') return `reference${b ? ` · ${b.replace('p', 'p.')}` : ''}`;
  if (kind === 'web') return `web ${a}`;
  if (kind === 'mem') return 'earlier answer';
  return a ?? kind;
}

interface Props {
  citation: Citation;
  onJump: (citation: Citation) => void;
}

/** A citation under an answer; clicking it jumps to the cited slide or attachment. */
export function CitationChip({ citation, onJump }: Props) {
  return (
    <button type="button" className="chip" title={citation.block_id} onClick={() => onJump(citation)}>
      {chipLabel(citation.block_id)}
    </button>
  );
}
