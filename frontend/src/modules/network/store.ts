import { create } from 'zustand';
import {
  cloneDocument,
  emptyDocument,
  migrateMcpNodes,
  snapPosition,
  type AgentNetworkDocument,
  type GraphEdge,
  type GraphNode,
} from '@/modules/network/model/document';
import { duplicateNodes } from '@/modules/network/model/serialize';
import { normalizeChannelEdges } from '@/modules/network/schema/channels';

const MAX_HISTORY = 50;
/** M23: keystrokes in one field within this gap are one undo step. */
const COALESCE_MS = 1000;

type EditorStore = {
  document: AgentNetworkDocument;
  saved: AgentNetworkDocument | null;
  selectedNodeIds: string[];
  selectedEdgeIds: string[];
  past: AgentNetworkDocument[];
  future: AgentNetworkDocument[];
  /** Bumped on every history step; a coalesced edit only merges into the same step. */
  historySeq: number;
  snap: boolean;
  showGrid: boolean;
  showMinimap: boolean;
  loadErrorKey?: string;
  hydrate: (doc: AgentNetworkDocument, saved: boolean) => void;
  resetNew: () => void;
  setMeta: (patch: Partial<Pick<AgentNetworkDocument, 'name' | 'description' | 'tags'>>) => void;
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;
  setNodes: (nodes: GraphNode[], record?: boolean) => void;
  setEdges: (edges: GraphEdge[], record?: boolean) => void;
  applyDocument: (doc: AgentNetworkDocument, record?: boolean) => void;
  addNode: (node: GraphNode) => void;
  select: (nodeIds: string[], edgeIds?: string[]) => void;
  setSnap: (snap: boolean) => void;
  setShowGrid: (show: boolean) => void;
  setShowMinimap: (show: boolean) => void;
  undo: () => void;
  redo: () => void;
  /** `sent` is the document as it went to the server (M24). */
  markSaved: (doc: AgentNetworkDocument, sent?: AgentNetworkDocument) => void;
  /** M25: derived values (window, threads, defaults); no undo step, not "changed". */
  normalizeNode: (id: string, patch: Record<string, unknown>) => void;
  isDirty: () => boolean;
};

function withoutHistory(doc: AgentNetworkDocument): string {
  const { viewport: _viewport, updatedAt: _updatedAt, ...rest } = doc;
  void _viewport;
  void _updatedAt;
  return JSON.stringify(rest);
}

export const useNetworkEditor = create<EditorStore>((set, get) => ({
  document: emptyDocument(),
  saved: null,
  selectedNodeIds: [],
  selectedEdgeIds: [],
  past: [],
  future: [],
  historySeq: 0,
  snap: true,
  showGrid: true,
  showMinimap: true,
  hydrate: (doc, saved) => {
    const next = migrateMcpNodes(normalizeChannelEdges(doc));
    set({
      document: cloneDocument(next),
      saved: saved ? cloneDocument(next) : null,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      past: [],
      future: [],
      historySeq: get().historySeq + 1,
      loadErrorKey: undefined,
    });
  },
  resetNew: () =>
    set({
      document: emptyDocument(),
      saved: null,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      past: [],
      future: [],
      historySeq: get().historySeq + 1,
      loadErrorKey: undefined,
    }),
  setMeta: (patch) => {
    const state = get();
    push(state, set, { ...state.document, ...patch });
  },
  setViewport: (viewport) => set({ document: { ...get().document, viewport } }),
  setNodes: (nodes, record = true) => {
    const state = get();
    const next = { ...state.document, nodes };
    if (record) push(state, set, next);
    else set({ document: next });
  },
  setEdges: (edges, record = true) => {
    const state = get();
    const next = { ...state.document, edges };
    if (record) push(state, set, next);
    else set({ document: next });
  },
  applyDocument: (doc, record = true) => {
    const state = get();
    if (record) push(state, set, doc);
    else set({ document: doc });
  },
  addNode: (node) =>
    set((state) => {
      const position = snapPosition(node.position, state.snap);
      return {
        document: { ...state.document, nodes: [...state.document.nodes, { ...node, position }] },
        past: [...state.past, cloneDocument(state.document)].slice(-MAX_HISTORY),
        future: [],
        historySeq: state.historySeq + 1,
        selectedNodeIds: [node.id],
        selectedEdgeIds: [],
      };
    }),
  select: (nodeIds, edgeIds = []) =>
    set((state) => {
      if (sameIds(state.selectedNodeIds, nodeIds) && sameIds(state.selectedEdgeIds, edgeIds)) return state;
      return { selectedNodeIds: nodeIds, selectedEdgeIds: edgeIds };
    }),
  setSnap: (snap) => set({ snap }),
  setShowGrid: (showGrid) => set({ showGrid }),
  setShowMinimap: (showMinimap) => set({ showMinimap }),
  undo: () => {
    const { past, document, future } = get();
    const previous = past[past.length - 1];
    if (!previous) return;
    set({
      document: previous,
      past: past.slice(0, -1),
      future: [cloneDocument(document), ...future].slice(0, MAX_HISTORY),
      historySeq: get().historySeq + 1,
      selectedNodeIds: [],
      selectedEdgeIds: [],
    });
  },
  redo: () => {
    const { past, document, future } = get();
    const next = future[0];
    if (!next) return;
    set({
      document: next,
      future: future.slice(1),
      past: [...past, cloneDocument(document)].slice(-MAX_HISTORY),
      historySeq: get().historySeq + 1,
      selectedNodeIds: [],
      selectedEdgeIds: [],
    });
  },
  markSaved: (doc, sent) => {
    const current = get().document;
    if (!sent || withoutHistory(current) === withoutHistory(sent)) {
      set({ document: cloneDocument(doc), saved: cloneDocument(doc) });
      return;
    }
    // M24: edits made while the request ran stay; the document only learns its id
    // (and the name the save gave it, unless that was edited too).
    set({
      document: {
        ...current,
        id: doc.id,
        updatedAt: doc.updatedAt,
        name: current.name === sent.name ? doc.name : current.name,
      },
      saved: cloneDocument(doc),
    });
  },
  normalizeNode: (id, patch) => {
    const state = get();
    const apply = (doc: AgentNetworkDocument): AgentNetworkDocument => ({
      ...doc,
      nodes: doc.nodes.map((node) => (node.id === id ? { ...node, data: { ...node.data, ...patch } } : node)),
    });
    const node = state.document.nodes.find((item) => item.id === id);
    if (!node || Object.entries(patch).every(([key, value]) => node.data[key] === value)) return;
    const savedNode = state.saved?.nodes.find((item) => item.id === id);
    set({
      document: apply(state.document),
      // The saved copy gets the same derived values, so they do not count as a change.
      saved: state.saved && savedNode ? apply(state.saved) : state.saved,
    });
  },
  isDirty: () => {
    const { document, saved } = get();
    if (!saved) return withoutHistory(document) !== withoutHistory(emptyDocument()) || Boolean(document.name);
    return withoutHistory(document) !== withoutHistory(saved);
  },
}));

function sameIds(a: string[], b: string[]) {
  if (a.length !== b.length) return false;
  return a.every((id, index) => id === b[index]);
}

function push(
  state: EditorStore,
  set: (partial: Partial<EditorStore>) => void,
  next: AgentNetworkDocument,
) {
  set({
    document: next,
    past: [...state.past, cloneDocument(state.document)].slice(-MAX_HISTORY),
    future: [],
    historySeq: state.historySeq + 1,
  });
}

export function editorAddNode(node: GraphNode) {
  useNetworkEditor.getState().addNode(node);
}

export function editorDeleteSelection() {
  const state = useNetworkEditor.getState();
  const nodeIds = new Set(state.selectedNodeIds);
  const edgeIds = new Set(state.selectedEdgeIds);
  if (nodeIds.size === 0 && edgeIds.size === 0) return;
  state.applyDocument({
    ...state.document,
    nodes: state.document.nodes.filter((node) => !nodeIds.has(node.id)),
    edges: state.document.edges.filter(
      (edge) => !edgeIds.has(edge.id) && !nodeIds.has(edge.source) && !nodeIds.has(edge.target),
    ),
  });
  state.select([]);
}

export function editorDuplicateSelection() {
  const state = useNetworkEditor.getState();
  if (state.selectedNodeIds.length === 0) return;
  const copied = duplicateNodes(state.document.nodes, state.document.edges, state.selectedNodeIds);
  state.applyDocument({
    ...state.document,
    nodes: [...state.document.nodes, ...copied.nodes],
    edges: [...state.document.edges, ...copied.edges],
  });
  state.select(copied.nodes.map((node) => node.id));
}

export function editorNudge(dx: number, dy: number) {
  const state = useNetworkEditor.getState();
  const selected = new Set(state.selectedNodeIds);
  if (selected.size === 0) return;
  const step = state.snap ? 16 : 1;
  state.applyDocument({
    ...state.document,
    nodes: state.document.nodes.map((node) =>
      selected.has(node.id)
        ? { ...node, position: { x: node.position.x + dx * step, y: node.position.y + dy * step } }
        : node,
    ),
  });
}

let lastEdit: { key: string; at: number; seq: number } | null = null;

export function editorUpdateNodeData(id: string, patch: Record<string, unknown>) {
  const state = useNetworkEditor.getState();
  const key = `${id}:${Object.keys(patch).sort().join(',')}`;
  const now = Date.now();
  // M23: typing into one field is one undo step, not one per key.
  const merge =
    lastEdit !== null && lastEdit.key === key && lastEdit.seq === state.historySeq && now - lastEdit.at < COALESCE_MS;
  state.applyDocument(
    {
      ...state.document,
      nodes: state.document.nodes.map((node) =>
        node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
      ),
    },
    !merge,
  );
  lastEdit = { key, at: now, seq: useNetworkEditor.getState().historySeq };
}

/** M25: a value the inspector derives, not one the user typed. */
export function editorNormalizeNodeData(id: string, patch: Record<string, unknown>) {
  useNetworkEditor.getState().normalizeNode(id, patch);
}
