import { getRun, listRunLogs, listRuns } from '@/modules/history/api';
import type { RunDetail } from '@/modules/history/model/types';
import { maskLog } from '@/modules/monitoring/model/mask';
import type { ChatMessage, LogEvent, NodeRuntime, RunGraph, RunSnapshot } from '@/modules/monitoring/model/types';

function asGraph(raw: RunDetail['graphSnapshot']): RunGraph {
  if (!raw || !Array.isArray(raw.nodes)) return { nodes: [], edges: [] };
  return {
    nodes: raw.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position ?? { x: 0, y: 0 },
      data: node.data ?? {},
    })),
    edges: (raw.edges ?? []).map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
    })),
  };
}

export function snapshotFromHistory(detail: RunDetail): RunSnapshot {
  const graph = asGraph(detail.graphSnapshot);
  const nodesRuntime: Record<string, NodeRuntime> = {};
  for (const node of graph.nodes) {
    nodesRuntime[node.id] = {
      status: detail.outcome === 'succeeded' ? 'done' : 'idle',
      role: typeof node.data.role === 'string' ? node.data.role : undefined,
    };
  }
  for (const step of detail.steps ?? []) {
    nodesRuntime[step.nodeId] = {
      status: step.status,
      role: step.role,
      waitReason: step.waitReason,
      error: step.errorMessage,
    };
  }
  const errorStep = (detail.steps ?? []).find((step) => step.status === 'error');
  let tokensIn = 0;
  let tokensOut = 0;
  for (const call of detail.calls ?? []) {
    tokensIn += call.tokensIn ?? 0;
    tokensOut += call.tokensOut ?? 0;
  }
  const chat: ChatMessage[] = (detail.chat ?? []).map((message) => ({
    id: message.id,
    runId: detail.runId,
    role: message.role,
    content: message.content,
    createdAt: message.createdAt,
  }));
  const done = Object.values(nodesRuntime).filter((node) => node.status === 'done').length;
  return {
    runId: detail.runId,
    networkId: detail.networkId,
    networkName: detail.networkName,
    startedAt: detail.startedAt,
    endedAt: detail.endedAt,
    outcome: detail.outcome,
    archived: true,
    serviceStatus: 'stopped',
    errorMessage: detail.errorMessage,
    graph,
    nodesRuntime,
    activity: {
      currentNodeIds: [],
      dag:
        graph.nodes.length > 0
          ? { completed: done, total: graph.nodes.length, pendingNodeIds: [] }
          : undefined,
      stepError:
        errorStep && errorStep.errorMessage
          ? { nodeId: errorStep.nodeId, message: errorStep.errorMessage }
          : undefined,
      tokens: { in: tokensIn || undefined, out: tokensOut },
    },
    chat: chat.length ? { messages: chat, generating: false } : undefined,
  };
}

export async function loadLatestHistoryRun(): Promise<{ run: RunSnapshot; logs: LogEvent[] } | null> {
  const { items } = await listRuns({ limit: 1 });
  const id = items[0]?.runId;
  if (!id) return null;
  const [detail, rawLogs] = await Promise.all([getRun(id), listRunLogs(id)]);
  if (!detail) return null;
  const run = snapshotFromHistory(detail);
  const logs = rawLogs.map((event) => {
    const masked = maskLog(event);
    return { ...event, ...masked } satisfies LogEvent;
  });
  return { run, logs };
}
