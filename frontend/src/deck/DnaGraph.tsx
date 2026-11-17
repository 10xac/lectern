import type { KeyboardEvent } from 'react';
import type { DnaGraph as Graph, DnaNode } from '../api';

const MIN_WIDTH = 420;
const SPACING = 104; // at least this many pixels per node in a row, so labels stay readable
const ROW = 92;
export const DEGREE_COLOURS: Record<string, string> = { high: '#CF1322', medium: '#FA8C16', low: '#52C41A', general: '#8C8C8C' };
const TYPE_FILL: Record<string, string> = { deck: '#4F46E5', slide: '#4F46E5', component: '#13C2C2', file: '#1677FF', url: '#1677FF' };
const short = (s: string) => (s.length > 20 ? `${s.slice(0, 19)}…` : s);

/** The drawing's width: wide enough for the fullest row (the panel scrolls sideways if needed). */
export function widthOf(graph: Graph): number {
  const counts: Record<number, number> = {};
  for (const n of graph.nodes) counts[n.layer] = (counts[n.layer] ?? 0) + 1;
  return Math.max(MIN_WIDTH, (Math.max(0, ...Object.values(counts)) + 1) * SPACING * 0.8);
}

/** Place nodes in rows by layer (deck and general influences on top, the slide at the bottom). */
export function layout(graph: Graph): Record<string, { x: number; y: number; flip: boolean }> {
  const width = widthOf(graph);
  const layers = [...new Set(graph.nodes.map((n) => n.layer))].sort((a, b) => a - b);
  const at: Record<string, { x: number; y: number; flip: boolean }> = {};
  layers.forEach((layer, row) => {
    const inRow = graph.nodes.filter((n) => n.layer === layer);
    // In a full row every other label goes above its node, so neighbours do not overlap.
    const dense = width / (inRow.length + 1) < SPACING;
    inRow.forEach((n, i) => (at[n.id] = { x: 24 + ((i + 1) * (width - 48)) / (inRow.length + 1), y: 40 + row * ROW, flip: dense && i % 2 === 1 }));
  });
  return at;
}

function Node({ n, at, onOpen }: { n: DnaNode; at: { x: number; y: number; flip: boolean }; onOpen: (id: string) => void }) {
  const isInfluence = n.type === 'influence';
  const open = () => isInfluence && onOpen(n.id.slice(4));
  const key = (e: KeyboardEvent) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open());
  const fill = n.degree ? DEGREE_COLOURS[n.degree] : (TYPE_FILL[n.type] ?? '#BFBFBF');
  return (
    <g data-testid="dna-node" transform={`translate(${at.x},${at.y})`} onClick={open} onKeyDown={key}
      role={isInfluence ? 'button' : undefined} tabIndex={isInfluence ? 0 : undefined}
      aria-label={isInfluence ? `Open influence ${n.label}` : undefined}
      className={isInfluence ? 'cursor-pointer outline-none [&:focus-visible>circle]:stroke-[#4F46E5] [&:hover>circle]:opacity-80' : undefined}>
      <circle r={isInfluence ? 11 : 8} fill={fill} stroke="#fff" strokeWidth={3} />
      {n.stale && <circle r={15} fill="none" stroke="#FAAD14" strokeDasharray="3 2" strokeWidth={1.5} />}
      <text y={at.flip ? -18 : isInfluence ? 27 : 24} textAnchor="middle" className="fill-[#595959] text-[11px]">{short(n.label)}{n.stale ? ' ⚠' : ''}</text>
      <title>{`${n.type}: ${n.label}${n.degree ? ` (${n.degree})` : ''}${n.stale ? ' — stale' : ''}`}</title>
    </g>
  );
}

/** The DNA as a layered SVG graph. Edge width and colour show the degree; click an influence to open it. */
export function DnaGraph({ graph, onOpen }: { graph: Graph; onOpen: (influenceId: string) => void }) {
  const at = layout(graph);
  const width = widthOf(graph);
  const rows = new Set(graph.nodes.map((n) => n.layer)).size;
  return (
    <div className="overflow-x-auto">
      <svg className="min-w-full" width={width} viewBox={`0 0 ${width} ${Math.max(rows, 1) * ROW}`} role="group" aria-label="DNA graph">
        {graph.edges.map((e, i) => (
          <line key={i} data-testid="dna-edge"
            x1={at[e.from]?.x} y1={at[e.from]?.y} x2={at[e.to]?.x} y2={at[e.to]?.y}
            stroke={e.degree ? DEGREE_COLOURS[e.degree] : '#D9D9D9'} strokeOpacity={0.75}
            strokeWidth={e.weight ? 1 + 4 * e.weight : 1.5}
            strokeDasharray={e.type === 'cites' || e.type === 'derived' ? '5 4' : undefined} />
        ))}
        {graph.nodes.map((n) => at[n.id] && <Node key={n.id} n={n} at={at[n.id]} onOpen={onOpen} />)}
      </svg>
    </div>
  );
}

/** What the colours mean. */
export function DnaLegend() {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-ink-muted" aria-label="Degree legend">
      {Object.entries(DEGREE_COLOURS).map(([d, c]) => (
        <li key={d} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} aria-hidden />{d}</li>
      ))}
      <li className="flex items-center gap-1"><span className="h-0 w-4 border-t border-dashed border-ink-muted" aria-hidden />cites</li>
    </ul>
  );
}
