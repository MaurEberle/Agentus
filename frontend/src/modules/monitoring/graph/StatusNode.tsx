import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { useEffect } from 'react';
import { Handle, Position, useUpdateNodeInternals, type Node, type NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { asGraphNode, type PortDef } from '@/modules/network/model/document';
import { handleTopPercent, nodeMinHeightPx, rfHandleId } from '@/modules/network/canvas/handles';
import { portI18nKey, portsFor, routerBranchName } from '@/modules/network/schema/ports';
import type { NodeRuntimeStatus, WaitReason } from '@/modules/monitoring/model/types';

const ICONS: Record<string, typeof Bot> = {
  chat_input: MessageSquare,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
  knowledge: Database,
  router: GitFork,
  end: CircleStop,
};

export type StatusNodeData = {
  displayName: string;
  nodeType: string;
  role?: string;
  status: NodeRuntimeStatus;
  waitReason?: WaitReason;
  nodeData?: Record<string, unknown>;
};

export type StatusFlowNode = Node<StatusNodeData, 'status'>;

export function statusNodeSize(nodeType: string, nodeData?: Record<string, unknown>, id = '_') {
  const graph = asGraphNode({
    id,
    type: nodeType,
    position: { x: 0, y: 0 },
    data: nodeData ?? {},
  });
  const ports = graph ? portsFor(graph) : [];
  return {
    width: 176,
    height: nodeMinHeightPx(
      ports.filter((port) => port.direction === 'in').length,
      ports.filter((port) => port.direction === 'out').length,
    ),
  };
}

const STATUS_CLASS: Record<NodeRuntimeStatus, string> = {
  idle: 'border-border',
  waiting: 'border-warning',
  running: 'border-primary ring-2 ring-primary',
  done: 'border-muted-foreground/40',
  error: 'border-destructive ring-2 ring-destructive',
};

export function StatusNode({ id, data, selected }: NodeProps<StatusFlowNode>) {
  const { t } = useTranslation();
  const updateNodeInternals = useUpdateNodeInternals();
  const Icon = ICONS[data.nodeType] ?? Bot;
  const role = data.role || t(`monitoring.nodeType.${data.nodeType}`, { defaultValue: data.nodeType });
  const graph = asGraphNode({
    id,
    type: data.nodeType,
    position: { x: 0, y: 0 },
    data: data.nodeData ?? {},
  });
  const ports = graph ? portsFor(graph) : [];
  const ins = ports.filter((port) => port.direction === 'in');
  const outs = ports.filter((port) => port.direction === 'out');
  const minHeight = nodeMinHeightPx(ins.length, outs.length);

  useEffect(() => {
    updateNodeInternals(id);
  }, [id, ins.length, outs.length, minHeight, updateNodeInternals]);

  return (
    <div
      className={cn(
        'relative min-w-40 overflow-visible rounded-lg border bg-card px-3 py-2 shadow-sm',
        STATUS_CLASS[data.status],
        selected && data.status !== 'error' && data.status !== 'running' && 'ring-2 ring-ring',
        data.status === 'running' && 'motion-safe:animate-pulse',
      )}
      style={{ minHeight }}
    >
      {ins.map((port, index) => (
        <ViewHandle
          key={`in-${port.id}`}
          graph={graph}
          port={port}
          index={index}
          count={ins.length}
          side="left"
        />
      ))}
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 shrink-0 text-muted-foreground" />
        <p className="truncate text-sm font-medium">{data.displayName}</p>
      </div>
      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{role}</p>
      <p
        className={cn(
          'mt-1 inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
          data.status === 'running' && 'bg-primary/15 text-primary',
          data.status === 'waiting' && 'bg-warning/15 text-warning-foreground',
          data.status === 'error' && 'bg-destructive/15 text-destructive',
          data.status === 'done' && 'bg-muted text-muted-foreground',
          data.status === 'idle' && 'bg-muted text-muted-foreground',
        )}
      >
        {t(`monitoring.nodeStatus.${data.status}`)}
      </p>
      {outs.map((port, index) => (
        <ViewHandle
          key={`out-${port.id}`}
          graph={graph}
          port={port}
          index={index}
          count={outs.length}
          side="right"
        />
      ))}
    </div>
  );
}

function ViewHandle({
  graph,
  port,
  index,
  count,
  side,
}: {
  graph: ReturnType<typeof asGraphNode>;
  port: PortDef;
  index: number;
  count: number;
  side: 'left' | 'right';
}) {
  const { t } = useTranslation();
  const name = (graph ? routerBranchName(graph, port.id) : undefined) ?? t(portI18nKey(port));
  return (
    <Handle
      id={rfHandleId(port)}
      type={port.direction === 'in' ? 'target' : 'source'}
      position={side === 'left' ? Position.Left : Position.Right}
      style={{ top: handleTopPercent(index, count) }}
      isConnectable={false}
      aria-label={name}
      title={name}
      className="!size-3 !rounded-full !border-2 !border-background !bg-primary"
    />
  );
}
