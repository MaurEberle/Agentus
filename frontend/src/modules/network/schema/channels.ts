import type { AgentNetworkDocument, GraphNode } from '@/modules/network/model/document';

/** Free orchestrator port. A drop on it becomes `channel:<agentId>`. */
export const CHANNEL_GHOST_ID = 'channel';

export function channelHandle(agentId: string): string {
  return `channel:${agentId}`;
}

export function agentIdFromChannel(handle: string | null | undefined): string | null {
  if (!handle?.startsWith('channel:')) return null;
  const id = handle.slice('channel:'.length);
  return id || null;
}

/** Old graphs hung every agent on the orchestrator message port. That port is only the end now. */
export function normalizeChannelEdges(doc: AgentNetworkDocument): AgentNetworkDocument {
  const byId = new Map(doc.nodes.map((node) => [node.id, node]));
  let changed = false;
  const edges = doc.edges.map((edge) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (
      source?.type === 'orchestrator' &&
      target?.type === 'agent' &&
      edge.sourceHandle === 'message' &&
      edge.targetHandle === 'message'
    ) {
      changed = true;
      return { ...edge, sourceHandle: channelHandle(target.id), targetHandle: CHANNEL_GHOST_ID };
    }
    return edge;
  });
  if (!changed) return doc;
  return { ...doc, edges };
}

export function channelLabel(agent: GraphNode | undefined, agentId: string): string {
  const name = agent && typeof agent.data.displayName === 'string' ? agent.data.displayName.trim() : '';
  return name || agentId;
}
