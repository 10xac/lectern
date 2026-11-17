import { Database, FileText, Globe, History, Presentation, Sparkles } from 'lucide-react';
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

const ICONS: Record<string, typeof Globe> = { slide: Presentation, att: Database, dna: Sparkles, file: FileText, web: Globe, mem: History };

/** Citation markers like [slide:4:notes] are shown as chips, so they are removed from the text. */
export const stripMarkers = (text: string) => text.replace(/\s*\[[a-z]+(?::[\w.-]+)+\]/g, '').trim();

/** A citation under an answer; clicking it jumps to the cited slide, data, influence or reference. */
export function CitationChip({ citation, onJump }: { citation: Citation; onJump: (citation: Citation) => void }) {
  const Icon = ICONS[citation.block_id.split(':')[0]] ?? FileText;
  return (
    <button
      type="button"
      title={citation.block_id}
      onClick={() => onJump(citation)}
      className="inline-flex h-6 items-center gap-1 rounded border border-line bg-surface px-2 text-xs text-ink-soft hover:border-brand hover:text-brand"
    >
      <Icon className="h-3 w-3" aria-hidden />
      {chipLabel(citation.block_id)}
    </button>
  );
}
