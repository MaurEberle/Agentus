import { useCallback, useEffect, useMemo } from 'react';
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
import { StatusNode, type StatusFlowNode } from '@/modules/monitoring/graph/StatusNode';
import { NodeDetail } from '@/modules/monitoring/graph/NodeDetail';
import { useMonitoringStore } from '@/modules/monitoring/store';

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
  const { fitView } = useReactFlow();

  const nodes: Node[] = useMemo(
    () =>
      run.graph.nodes.map((node) => {
        const runtime = run.nodesRuntime[node.id];
        return {
          id: node.id,
          type: 'status',
          position: node.position,
          selected: selectedNodeId === node.id,
          data: {
            displayName: nodeDisplayName(node),
            nodeType: node.type,
            role: runtime?.role,
            status: runtime?.status ?? 'idle',
            waitReason: runtime?.waitReason,
          },
        } satisfies StatusFlowNode;
      }),
    [run.graph.nodes, run.nodesRuntime, selectedNodeId],
  );

  const edges: Edge[] = useMemo(
    () =>
      run.graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
      })),
    [run.graph.edges],
  );

  const graphKey = `${run.runId}:${run.graph.nodes.map((node) => node.id).join(',')}`;
  useEffect(() => {
    void fitView({ padding: 0.2 });
  }, [fitView, graphKey]);

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
    <div className={cn('relative h-[280px] md:h-full md:min-h-[320px]', dimmed && 'opacity-60')}>
      <FitButton />
      <ReactFlow
        className="monitoring-flow"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        zoomOnScroll
        fitView
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
    <Card className="flex min-h-0 flex-col">
      <CardHeader className="pb-2">
        <CardTitle>{t('monitoring.graph.title')}</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0 pb-3">
        <ReactFlowProvider>
          <GraphInner run={run} dimmed={dimmed} />
        </ReactFlowProvider>
        <NodeDetail run={run} />
      </CardContent>
    </Card>
  );
}
