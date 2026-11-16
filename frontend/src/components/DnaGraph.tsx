import type { DnaGraph as Graph, DnaNode } from '../api';

const WIDTH = 640;
const ROW = 90;
const COLOURS: Record<string, string> = { high: '#c2410c', medium: '#d97706', low: '#65a30d', general: '#64748b' };
const short = (s: string) => (s.length > 22 ? `${s.slice(0, 21)}…` : s);

/** Place nodes in rows by layer (deck and general influences on top, the slide at the bottom). */
export function layout(graph: Graph): Record<string, { x: number; y: number }> {
  const layers = [...new Set(graph.nodes.map((n) => n.layer))].sort((a, b) => a - b);
  const at: Record<string, { x: number; y: number }> = {};
  layers.forEach((layer, row) => {
    const inRow = graph.nodes.filter((n) => n.layer === layer);
    inRow.forEach((n, i) => (at[n.id] = { x: ((i + 1) * WIDTH) / (inRow.length + 1), y: 30 + row * ROW }));
  });
  return at;
}

/** The DNA as a layered SVG graph. Edge width and colour show the degree; click an influence to open it. */
export function DnaGraph({ graph, onOpen }: { graph: Graph; onOpen: (influenceId: string) => void }) {
  const at = layout(graph);
  const rows = new Set(graph.nodes.map((n) => n.layer)).size;
  const click = (n: DnaNode) => n.type === 'influence' && onOpen(n.id.slice(4));
  return (
    <svg className="dna-graph" viewBox={`0 0 ${WIDTH} ${rows * ROW}`} role="img" aria-label="DNA graph">
      {graph.edges.map((e, i) => (
        <line
          key={i}
          data-testid="dna-edge"
          className={`edge ${e.type}`}
          x1={at[e.from]?.x} y1={at[e.from]?.y} x2={at[e.to]?.x} y2={at[e.to]?.y}
          stroke={e.degree ? COLOURS[e.degree] : '#94a3b8'}
          strokeWidth={e.weight ? 1 + 4 * e.weight : 1}
          strokeDasharray={e.type === 'cites' || e.type === 'derived' ? '4 3' : undefined}
        />
      ))}
      {graph.nodes.map((n) => (
        <g key={n.id} data-testid="dna-node" className={`node ${n.type}${n.stale ? ' stale' : ''}`}
           transform={`translate(${at[n.id].x},${at[n.id].y})`} onClick={() => click(n)}>
          <circle r={n.type === 'influence' ? 9 : 6} fill={n.degree ? COLOURS[n.degree] : '#cbd5e1'} />
          <text y={22} textAnchor="middle">{short(n.label)}{n.stale ? ' ⚠' : ''}</text>
          <title>{`${n.type}: ${n.label}${n.degree ? ` (${n.degree})` : ''}`}</title>
        </g>
      ))}
    </svg>
  );
}
