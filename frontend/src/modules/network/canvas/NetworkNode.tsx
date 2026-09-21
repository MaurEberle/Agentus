import { Handle, Position, useConnection, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import {
  Bot,
  CircleStop,
  Database,
  GitFork,
  MessageSquare,
  Sparkles,
  Waypoints,
  Wrench,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import type { GraphNode, PortDef, ValidationIssue } from '@/modules/network/model/document';
import { displayNameOf } from '@/modules/network/model/document';
import {
  handleTopPercent,
  nodeMinHeightPx,
  portStateKey,
  rfHandleId,
} from '@/modules/network/canvas/handles';
import { portAcceptsConnection, portI18nKey, portsFor, routerBranchName, type PortContext } from '@/modules/network/schema/ports';

const ICONS = {
  chat_input: MessageSquare,
  orchestrator: Waypoints,
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
  portContext?: PortContext;
};

type ConnectMatch = 'idle' | 'origin' | 'match' | 'mismatch';

export function NetworkNode({ id, data, selected }: NodeProps) {
  const { t } = useTranslation();
  const nodeData = data as unknown as NetworkNodeData;
  const node = nodeData.graph;
  const portContext = nodeData.portContext;
  const Icon = ICONS[node.type];
  const ports = portsFor(node, portContext);
  const ins = ports.filter((port) => port.direction === 'in');
  const outs = ports.filter((port) => port.direction === 'out');
  const invalid = nodeData.issues.length > 0;
  const connected = useMemo(() => new Set(nodeData.connected ?? []), [nodeData.connected]);
  const connecting = useConnection((state) => state.inProgress);
  const fromHandle = useConnection((state) => state.fromHandle);
  const fromNode = useConnection((state) => state.fromNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const minHeight = nodeMinHeightPx(ins.length, outs.length);
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  const fromGraph = (fromNode?.data as NetworkNodeData | undefined)?.graph;

  useEffect(() => {
    updateNodeInternals(id);
  }, [id, ins.length, outs.length, minHeight, updateNodeInternals]);

  function matchFor(port: PortDef): ConnectMatch {
    if (!connecting || !fromGraph || !fromHandle) return 'idle';
    if (fromGraph.id === node.id && fromHandle.id === rfHandleId(port)) return 'origin';
    const accepts = portAcceptsConnection(
      node,
      port,
      {
        node: fromGraph,
        handleId: fromHandle.id,
        handleType: fromHandle.type,
      },
      portContext,
    );
    return accepts ? 'match' : 'mismatch';
  }

  function labelOf(port: PortDef): string {
    return port.label ?? routerBranchName(node, port.id) ?? t(portI18nKey(port));
  }

  function showsIdle(port: PortDef, count: number): boolean {
    return count > 1 || (Boolean(port.required) && !connected.has(portStateKey(port)));
  }

  const leftIdle = ins.filter((port) => showsIdle(port, ins.length)).map(labelOf);
  const rightIdle = outs.filter((port) => showsIdle(port, outs.length)).map(labelOf);
  const widestLeft = leftIdle.reduce((best, name) => (name.length > best.length ? name : best), '');
  const widestRight = rightIdle.reduce((best, name) => (name.length > best.length ? name : best), '');

  return (
    <div
      className={cn(
        'group/node relative flex items-stretch gap-3 overflow-visible rounded-lg border bg-card px-3 shadow-sm',
        invalid ? 'border-destructive' : 'border-border',
        selected && (invalid ? 'ring-2 ring-destructive' : 'ring-2 ring-ring'),
        nodeData.readOnly && 'opacity-80',
      )}
      style={{ minHeight, minWidth: 160 }}
    >
      {ins.map((port, index) => {
        const match = matchFor(port);
        return (
          <PortHandle
            key={`in-${port.id}`}
            node={node}
            port={port}
            index={index}
            count={ins.length}
            side="left"
            connected={connected.has(portStateKey(port))}
            readOnly={Boolean(nodeData.readOnly)}
            match={match}
            showFullLabel={match === 'match' || (match !== 'mismatch' && hoveredKey === portStateKey(port))}
            onHover={setHoveredKey}
          />
        );
      })}
      {widestLeft ? (
        <PortNameColumn
          widest={widestLeft}
          ports={ins}
          node={node}
          connected={connected}
          matchFor={matchFor}
          hoveredKey={hoveredKey}
        />
      ) : null}
      <div className="flex min-w-0 flex-1 items-center gap-2 py-2">
        <Icon className="size-4 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted-foreground">{t(`network.palette.${node.type}`)}</p>
          <p className="truncate text-sm font-medium">{displayNameOf(node)}</p>
        </div>
      </div>
      {widestRight ? (
        <PortNameColumn
          widest={widestRight}
          ports={outs}
          node={node}
          connected={connected}
          matchFor={matchFor}
          hoveredKey={hoveredKey}
          align="right"
        />
      ) : null}
      {outs.map((port, index) => {
        const match = matchFor(port);
        return (
          <PortHandle
            key={`out-${port.id}`}
            node={node}
            port={port}
            index={index}
            count={outs.length}
            side="right"
            connected={connected.has(portStateKey(port))}
            readOnly={Boolean(nodeData.readOnly)}
            match={match}
            showFullLabel={match === 'match' || (match !== 'mismatch' && hoveredKey === portStateKey(port))}
            onHover={setHoveredKey}
          />
        );
      })}
    </div>
  );
}

function PortNameColumn({
  widest,
  ports,
  node,
  connected,
  matchFor,
  hoveredKey,
  align = 'left',
}: {
  widest: string;
  ports: PortDef[];
  node: GraphNode;
  connected: Set<string>;
  matchFor: (port: PortDef) => ConnectMatch;
  hoveredKey: string | null;
  align?: 'left' | 'right';
}) {
  const { t } = useTranslation();
  return (
    <div className="relative w-max shrink-0 self-stretch">
      <span className="invisible block whitespace-nowrap text-[10px] font-medium leading-tight" aria-hidden>
        {widest}
      </span>
      {ports.map((port, index) => {
        const unconfigured = Boolean(port.required) && !connected.has(portStateKey(port));
        const show = ports.length > 1 || unconfigured;
        if (!show) return null;
        const match = matchFor(port);
        const name = port.label ?? routerBranchName(node, port.id) ?? t(portI18nKey(port));
        const hideForHover = match === 'match' || (match !== 'mismatch' && hoveredKey === portStateKey(port));
        return (
          <span
            key={portStateKey(port)}
            className={cn(
              'pointer-events-none absolute top-0 -translate-y-1/2 whitespace-nowrap text-[10px] font-medium leading-tight',
              align === 'right' ? 'right-0 text-right' : 'left-0 text-left',
              unconfigured ? 'text-destructive' : 'text-muted-foreground',
              match === 'mismatch' && 'opacity-25',
              hideForHover && 'opacity-0',
            )}
            style={{ top: handleTopPercent(index, ports.length) }}
            aria-hidden
          >
            {name}
          </span>
        );
      })}
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
  match,
  showFullLabel,
  onHover,
}: {
  node: GraphNode;
  port: PortDef;
  index: number;
  count: number;
  side: 'left' | 'right';
  connected: boolean;
  readOnly: boolean;
  match: ConnectMatch;
  showFullLabel: boolean;
  onHover: (key: string | null) => void;
}) {
  const { t } = useTranslation();
  const key = portStateKey(port);
  const unconfigured = Boolean(port.required) && !connected;
  const name = port.label ?? routerBranchName(node, port.id) ?? t(portI18nKey(port));
  const directionLabel = t(`network.ports.${port.direction}`);
  const fullLabel = `${name} · ${directionLabel}`;
  const top = handleTopPercent(index, count);

  return (
    <>
      <Handle
        id={rfHandleId(port)}
        type={port.direction === 'in' ? 'target' : 'source'}
        position={side === 'left' ? Position.Left : Position.Right}
        style={{ top }}
        isConnectable={!readOnly && match !== 'mismatch'}
        aria-label={fullLabel}
        data-port-id={port.id}
        data-port-kind={port.kind}
        data-port-dir={port.direction}
        data-port-required={port.required ? 'true' : 'false'}
        data-port-connected={connected ? 'true' : 'false'}
        data-port-match={match}
        onMouseEnter={() => onHover(key)}
        onMouseLeave={() => onHover(null)}
        className={cn(
          '!rounded-full !border-2 !border-background motion-reduce:transition-none',
          unconfigured ? '!bg-destructive' : '!bg-primary',
          match === 'match' && '!size-3.5 !shadow-[0_0_0_3px_hsl(var(--primary)/0.5)]',
          match === 'origin' && '!size-3 !shadow-[0_0_0_2px_hsl(var(--primary)/0.4)]',
          match === 'mismatch' && '!size-2.5 opacity-25',
          match === 'idle' && '!size-3',
        )}
      />
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
