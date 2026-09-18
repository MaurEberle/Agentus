import { create } from 'zustand';
import {
  cloneDocument,
  emptyDocument,
  snapPosition,
  type AgentNetworkDocument,
  type GraphEdge,
  type GraphNode,
} from '@/modules/network/model/document';
import { duplicateNodes } from '@/modules/network/model/serialize';

const MAX_HISTORY = 50;

type EditorStore = {
  document: AgentNetworkDocument;
  saved: AgentNetworkDocument | null;
  selectedNodeIds: string[];
  selectedEdgeIds: string[];
  past: AgentNetworkDocument[];
  future: AgentNetworkDocument[];
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
  markSaved: (doc: AgentNetworkDocument) => void;
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
  snap: true,
  showGrid: true,
  showMinimap: true,
  hydrate: (doc, saved) =>
    set({
      document: cloneDocument(doc),
      saved: saved ? cloneDocument(doc) : null,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      past: [],
      future: [],
      loadErrorKey: undefined,
    }),
  resetNew: () =>
    set({
      document: emptyDocument(),
      saved: null,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      past: [],
      future: [],
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
      selectedNodeIds: [],
      selectedEdgeIds: [],
    });
  },
  markSaved: (doc) => set({ document: cloneDocument(doc), saved: cloneDocument(doc) }),
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

export function editorUpdateNodeData(id: string, patch: Record<string, unknown>) {
  const state = useNetworkEditor.getState();
  state.applyDocument({
    ...state.document,
    nodes: state.document.nodes.map((node) =>
      node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
    ),
  });
}
