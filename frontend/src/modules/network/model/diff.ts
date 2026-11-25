/** What changed between two network documents (backend: app/networks/diff.py). */
export type DiffEdge = { source: string; sourceHandle?: string; target: string; targetHandle?: string };

export type NetworkDiff = {
  head: string[];
  added: string[];
  removed: string[];
  changed: { id: string; fields: string[] }[];
  moved: string[];
  edgesAdded: DiffEdge[];
  edgesRemoved: DiffEdge[];
  /** Type and label of every node the diff names, from either side. */
  nodes: Record<string, { type: string; label: string }>;
  empty: boolean;
};

/** Graph marks: nodes the "after" side adds or changes. */
export function diffMarks(diff: NetworkDiff | null | undefined): Record<string, 'added' | 'changed'> {
  const out: Record<string, 'added' | 'changed'> = {};
  for (const id of diff?.added ?? []) out[id] = 'added';
  for (const item of diff?.changed ?? []) out[item.id] = 'changed';
  return out;
}
