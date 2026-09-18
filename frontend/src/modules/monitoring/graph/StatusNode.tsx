import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Wrench,
} from 'lucide-react';
import type { Node, NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
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
};

export type StatusFlowNode = Node<StatusNodeData, 'status'>;

const STATUS_CLASS: Record<NodeRuntimeStatus, string> = {
  idle: 'border-border',
  waiting: 'border-warning',
  running: 'border-primary ring-2 ring-primary',
  done: 'border-muted-foreground/40',
  error: 'border-destructive ring-2 ring-destructive',
};

export function StatusNode({ data, selected }: NodeProps<StatusFlowNode>) {
  const { t } = useTranslation();
  const Icon = ICONS[data.nodeType] ?? Bot;
  const role = data.role || t(`monitoring.nodeType.${data.nodeType}`, { defaultValue: data.nodeType });
  return (
    <div
      className={cn(
        'min-w-40 rounded-lg border bg-card px-3 py-2 shadow-sm',
        STATUS_CLASS[data.status],
        selected && data.status !== 'error' && data.status !== 'running' && 'ring-2 ring-ring',
        data.status === 'running' && 'motion-safe:animate-pulse',
      )}
    >
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
    </div>
  );
}
