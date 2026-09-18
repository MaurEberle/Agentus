import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { GraphNode, ValidationIssue } from '@/modules/network/model/document';
import { displayNameOf } from '@/modules/network/model/document';
import { rfHandleId } from '@/modules/network/canvas/handles';
import { portsFor } from '@/modules/network/schema/ports';

const ICONS = {
  chat_input: MessageSquare,
  llm: Sparkles,
  agent: Bot,
  tool: Wrench,
  knowledge: Database,
  router: GitFork,
  end: CircleStop,
};

export type NetworkNodeData = {
  graph: GraphNode;
  issues: ValidationIssue[];
  readOnly?: boolean;
};

export function NetworkNode({ data, selected }: NodeProps) {
  const { t } = useTranslation();
  const nodeData = data as unknown as NetworkNodeData;
  const node = nodeData.graph;
  const Icon = ICONS[node.type];
  const ports = portsFor(node);
  const ins = ports.filter((port) => port.direction === 'in');
  const outs = ports.filter((port) => port.direction === 'out');
  const invalid = nodeData.issues.length > 0;

  return (
    <div
      className={cn(
        'min-w-44 rounded-lg border bg-card px-3 py-2 shadow-sm',
        selected && 'ring-2 ring-ring',
        invalid && 'border-destructive',
        nodeData.readOnly && 'opacity-80',
      )}
    >
      {ins.map((port, index) => (
        <Handle
          key={`in-${port.id}`}
          id={rfHandleId(port)}
          type="target"
          position={Position.Left}
          style={{ top: 18 + index * 16 }}
          title={port.id}
          className="!size-2.5 !border-2 !border-background !bg-primary"
        />
      ))}
      <div className="flex items-center gap-2">
        <Icon className="size-4 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted-foreground">{t(`network.palette.${node.type}`)}</p>
          <p className="truncate text-sm font-medium">{displayNameOf(node)}</p>
        </div>
        {invalid ? <Badge variant="destructive">{t('network.badge.invalid')}</Badge> : null}
      </div>
      {outs.map((port, index) => (
        <Handle
          key={`out-${port.id}`}
          id={rfHandleId(port)}
          type="source"
          position={Position.Right}
          style={{ top: 18 + index * 16 }}
          title={port.id}
          className="!size-2.5 !border-2 !border-background !bg-primary"
        />
      ))}
    </div>
  );
}
