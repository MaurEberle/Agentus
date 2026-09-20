import { useCallback, useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { nodeDisplayName } from '@/modules/monitoring/model/graph';
import type { RunSnapshot } from '@/modules/monitoring/model/types';
import { StatusNode, statusNodeSize, type StatusFlowNode } from '@/modules/monitoring/graph/StatusNode';
import { NodeDetail } from '@/modules/monitoring/graph/NodeDetail';
import { useFitGraph } from '@/modules/monitoring/graph/useFitGraph';
import { useMonitoringStore } from '@/modules/monitoring/store';
import { asGraphNode } from '@/modules/network/model/document';
import { toRfHandlePair } from '@/modules/network/canvas/handles';

const nodeTypes = { status: StatusNode };

function FitButton() {
  const { t } = useTranslation();
  const { fitView } = useReactFlow();
  return (
    <Button type="button" size="sm" variant="outline" className="absolute right-2 top-2 z-10" onClick={() => void fitView({ padding: 0.2 })}>
      {t('monitoring.graph.fit')}
    </Button>
  );
}

function GraphInner({
  run,
  dimmed,
}: {
  run: RunSnapshot;
  dimmed?: boolean;
}) {
  const selectedNodeId = useMonitoringStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useMonitoringStore((state) => state.setSelectedNodeId);
  const setLogNodeId = useMonitoringStore((state) => state.setLogNodeId);
  const setTab = useMonitoringStore((state) => state.setTab);
  const clearLogFilter = useMonitoringStore((state) => state.clearLogFilter);
  const nodes: Node[] = useMemo(
    () =>
      run.graph.nodes.map((node) => {
        const runtime = run.nodesRuntime[node.id];
        const size = statusNodeSize(node.type, node.data, node.id);
        return {
          id: node.id,
          type: 'status',
          position: node.position,
          selected: selectedNodeId === node.id,
          className: 'overflow-visible',
          width: size.width,
          height: size.height,
          data: {
            displayName: nodeDisplayName(node),
            nodeType: node.type,
            role: runtime?.role,
            status: runtime?.status ?? 'idle',
            waitReason: runtime?.waitReason,
            nodeData: node.data,
          },
        } satisfies StatusFlowNode;
      }),
    [run.graph.nodes, run.nodesRuntime, selectedNodeId],
  );

  const edges: Edge[] = useMemo(
    () =>
      run.graph.edges.map((edge) => {
        const sourceNode = run.graph.nodes.find((node) => node.id === edge.source);
        const targetNode = run.graph.nodes.find((node) => node.id === edge.target);
        const handles = toRfHandlePair(
          sourceNode ? asGraphNode(sourceNode) : undefined,
          targetNode ? asGraphNode(targetNode) : undefined,
          edge,
        );
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
        };
      }),
    [run.graph.edges, run.graph.nodes],
  );

  const graphKey = `${run.runId}:${run.graph.nodes.map((node) => node.id).join(',')}`;
  const paneRef = useFitGraph(graphKey, nodes.length);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (selectedNodeId === node.id) {
        setSelectedNodeId(null);
        clearLogFilter();
        return;
      }
      setSelectedNodeId(node.id);
      setLogNodeId(node.id);
      setTab('log');
    },
    [clearLogFilter, selectedNodeId, setLogNodeId, setSelectedNodeId, setTab],
  );

  return (
    <div ref={paneRef} className={cn('absolute inset-0', dimmed && 'opacity-60')}>
      <FitButton />
      <ReactFlow
        className="monitoring-flow h-full w-full"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        zoomOnScroll
        fitView
        fitViewOptions={{ padding: 0.2 }}
        onInit={(instance) => {
          void instance.fitView({ padding: 0.2, duration: 0 });
        }}
        proOptions={{ hideAttribution: true }}
        onNodeClick={onNodeClick}
        onPaneClick={() => setSelectedNodeId(null)}
        minZoom={0.3}
        maxZoom={1.6}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable className="!h-20 !w-28" />
      </ReactFlow>
    </div>
  );
}

export function MiniGraph({ run, dimmed }: { run: RunSnapshot; dimmed?: boolean }) {
  const { t } = useTranslation();
  return (
    <Card className="flex h-full max-h-[1000px] min-h-0 flex-col overflow-hidden">
      <CardHeader className="shrink-0 pb-2">
        <CardTitle>{t('monitoring.graph.title')}</CardTitle>
      </CardHeader>
      <CardContent className="relative min-h-0 flex-1 p-0">
        <ReactFlowProvider>
          <GraphInner run={run} dimmed={dimmed} />
        </ReactFlowProvider>
        <NodeDetail run={run} />
      </CardContent>
    </Card>
  );
}
