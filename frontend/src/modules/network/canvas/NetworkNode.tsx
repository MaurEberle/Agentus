import { Handle, Position, useConnection, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { GraphNode, PortDef, ValidationIssue } from '@/modules/network/model/document';
import { displayNameOf } from '@/modules/network/model/document';
import {
  handleTopPercent,
  nodeMinHeightPx,
  portStateKey,
  rfHandleId,
} from '@/modules/network/canvas/handles';
import { portI18nKey, portsFor, routerBranchName } from '@/modules/network/schema/ports';

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
  connected: string[];
};

export function NetworkNode({ id, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const nodeData = data as unknown as NetworkNodeData;
  const node = nodeData.graph;
  const Icon = ICONS[node.type];
  const ports = portsFor(node);
  const ins = ports.filter((port) => port.direction === 'in');
  const outs = ports.filter((port) => port.direction === 'out');
  const invalid = nodeData.issues.length > 0;
  const connected = useMemo(() => new Set(nodeData.connected ?? []), [nodeData.connected]);
  const connecting = useConnection((state) => state.inProgress);
  const updateNodeInternals = useUpdateNodeInternals();
  const minHeight = nodeMinHeightPx(ins.length, outs.length);
  const multi = Math.max(ins.length, outs.length) > 1;
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  useEffect(() => {
    updateNodeInternals(id);
  }, [id, ins.length, outs.length, minHeight, updateNodeInternals]);

  return (
    <div
      className={cn(
        'group/node relative flex items-center overflow-visible rounded-lg border bg-card py-2 shadow-sm',
        multi ? 'min-w-64 px-16' : 'min-w-44 px-3',
        selected && 'ring-2 ring-ring',
        invalid && 'border-destructive',
        nodeData.readOnly && 'opacity-80',
      )}
      style={{ minHeight }}
    >
      {ins.map((port, index) => (
        <PortHandle
          key={`in-${port.id}`}
          node={node}
          port={port}
          index={index}
          count={ins.length}
          side="left"
          connected={connected.has(portStateKey(port))}
          readOnly={Boolean(nodeData.readOnly)}
          showFullLabel={connecting || hoveredKey === portStateKey(port)}
          showIdleName={ins.length > 1}
          onHover={setHoveredKey}
        />
      ))}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <Icon className="size-4 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted-foreground">{t(`network.palette.${node.type}`)}</p>
          <p className="truncate text-sm font-medium">{displayNameOf(node)}</p>
        </div>
        {invalid ? <Badge variant="destructive">{t('network.badge.invalid')}</Badge> : null}
      </div>
      {outs.map((port, index) => (
        <PortHandle
          key={`out-${port.id}`}
          node={node}
          port={port}
          index={index}
          count={outs.length}
          side="right"
          connected={connected.has(portStateKey(port))}
          readOnly={Boolean(nodeData.readOnly)}
          showFullLabel={connecting || hoveredKey === portStateKey(port)}
          showIdleName={outs.length > 1}
          onHover={setHoveredKey}
        />
      ))}
    </div>
  );
}

function PortHandle({
  node,
  port,
  index,
  count,
  side,
  connected,
  readOnly,
  showFullLabel,
  showIdleName,
  onHover,
}: {
  node: GraphNode;
  port: PortDef;
  index: number;
  count: number;
  side: 'left' | 'right';
  connected: boolean;
  readOnly: boolean;
  showFullLabel: boolean;
  showIdleName: boolean;
  onHover: (key: string | null) => void;
}) {
  const { t } = useTranslation();
  const key = portStateKey(port);
  const unconfigured = Boolean(port.required) && !connected;
  const name = routerBranchName(node, port.id) ?? t(portI18nKey(port));
  const directionLabel = t(`network.ports.${port.direction}`);
  const fullLabel = unconfigured
    ? `${name} · ${directionLabel} · ${t('network.ports.required')}`
    : `${name} · ${directionLabel}`;
  const top = handleTopPercent(index, count);

  return (
    <>
      <Handle
        id={rfHandleId(port)}
        type={port.direction === 'in' ? 'target' : 'source'}
        position={side === 'left' ? Position.Left : Position.Right}
        style={{ top }}
        isConnectable={!readOnly}
        aria-label={fullLabel}
        data-port-id={port.id}
        data-port-kind={port.kind}
        data-port-dir={port.direction}
        data-port-required={port.required ? 'true' : 'false'}
        data-port-connected={connected ? 'true' : 'false'}
        onMouseEnter={() => onHover(key)}
        onMouseLeave={() => onHover(null)}
        className={cn(
          '!size-3 !rounded-full !border-2 !border-background',
          unconfigured ? '!bg-destructive' : '!bg-primary',
        )}
      />
      {showIdleName || unconfigured ? (
        <span
          className={cn(
            'pointer-events-none absolute z-10 max-w-14 -translate-y-1/2 truncate text-[10px] font-medium leading-tight',
            side === 'left' ? 'left-3 text-left' : 'right-3 text-right',
            unconfigured ? 'text-destructive' : 'text-muted-foreground',
            showFullLabel && 'opacity-0',
          )}
          style={{ top }}
          aria-hidden
        >
          {name}
        </span>
      ) : null}
      <div
        className={cn(
          'pointer-events-none absolute z-20 -translate-y-1/2 transition-opacity motion-reduce:transition-none',
          showFullLabel ? 'opacity-100' : 'opacity-0',
          side === 'left' ? 'right-full mr-2' : 'left-full ml-2',
        )}
        style={{ top }}
        aria-hidden
      >
        <span
          className={cn(
            'block whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium leading-tight shadow-sm',
            unconfigured ? 'bg-destructive text-destructive-foreground' : 'bg-foreground text-background',
          )}
        >
          {fullLabel}
        </span>
      </div>
    </>
  );
}
