import type { AgentNetworkDocument, GraphEdge, GraphNode } from '@/modules/network/model/document';
import { cloneDocument, newId } from '@/modules/network/model/document';
import { agentIdFromChannel, channelHandle, normalizeChannelEdges } from '@/modules/network/schema/channels';

const SECRET_KEYS = /^(secret|password|token|apiKey|authorization|bearer)$/i;

export function stripSecrets<T extends Record<string, unknown>>(data: T): T {
  const next = { ...data };
  for (const key of Object.keys(next)) {
    if (SECRET_KEYS.test(key)) delete next[key];
  }
  return next;
}

export function sanitizeDocument(doc: AgentNetworkDocument): AgentNetworkDocument {
  return normalizeChannelEdges({
    ...cloneDocument(doc),
    schemaVersion: 1,
    nodes: doc.nodes.map((node) => ({
      ...node,
      data: stripSecrets({ ...node.data }),
    })),
  });
}

export function exportDocument(doc: AgentNetworkDocument): AgentNetworkDocument & { exportedAt: string } {
  const clean = sanitizeDocument(doc);
  return { ...clean, exportedAt: new Date().toISOString() };
}

export function duplicateNodes(
  nodes: GraphNode[],
  edges: GraphEdge[],
  ids: string[],
  offset = { x: 32, y: 32 },
): { nodes: GraphNode[]; edges: GraphEdge[]; idMap: Map<string, string> } {
  const selected = new Set(ids);
  const idMap = new Map<string, string>();
  const copiedNodes = nodes
    .filter((node) => selected.has(node.id))
    .map((node) => {
      const id = newId(node.type);
      idMap.set(node.id, id);
      return {
        ...structuredClone(node),
        id,
        position: { x: node.position.x + offset.x, y: node.position.y + offset.y },
      };
    });
  const copiedEdges = edges
    .filter((edge) => selected.has(edge.source) && selected.has(edge.target))
    .map((edge) => {
      const target = idMap.get(edge.target) as string;
      return {
        ...edge,
        id: newId('e'),
        source: idMap.get(edge.source) as string,
        sourceHandle: retargetChannel(edge.sourceHandle, idMap),
        target,
        targetHandle: edge.targetHandle,
      };
    });
  return { nodes: copiedNodes, edges: copiedEdges, idMap };
}

function retargetChannel(handle: string, idMap: Map<string, string>): string {
  const agentId = agentIdFromChannel(handle);
  if (!agentId) return handle;
  const next = idMap.get(agentId);
  return next ? channelHandle(next) : handle;
}

export function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
