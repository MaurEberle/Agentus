import { useEffect, useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { StatusNode, type StatusFlowNode } from '@/modules/monitoring/graph/StatusNode';
import type { GraphSnapshot, RunStep } from '@/modules/history/model/types';
import { asGraphNode } from '@/modules/network/model/document';
import { toRfHandlePair } from '@/modules/network/canvas/handles';

const nodeTypes = { status: StatusNode };

function FitButton() {
  const { t } = useTranslation();
  const { fitView } = useReactFlow();
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className="absolute right-2 top-2 z-10"
      onClick={() => void fitView({ padding: 0.2 })}
    >
      {t('history.graph.fit')}
    </Button>
  );
}

function Inner({ graph, steps }: { graph: GraphSnapshot; steps?: RunStep[] }) {
  const { fitView } = useReactFlow();
  const statusById = useMemo(() => {
    const map = new Map(steps?.map((step) => [step.nodeId, step]) ?? []);
    return map;
  }, [steps]);

  const nodes: Node[] = useMemo(
    () =>
      graph.nodes.map((node) => {
        const step = statusById.get(node.id);
        const name =
          typeof node.data.displayName === 'string' && node.data.displayName.trim()
            ? node.data.displayName
            : node.type;
        return {
          id: node.id,
          type: 'status',
          position: node.position,
          className: 'overflow-visible',
          data: {
            displayName: name,
            nodeType: node.type,
            role: step?.role ?? (typeof node.data.role === 'string' ? node.data.role : undefined),
            status: step?.status ?? 'done',
            waitReason: step?.waitReason,
            nodeData: node.data,
          },
        } satisfies StatusFlowNode;
      }),
    [graph.nodes, statusById],
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((edge) => {
        const sourceNode = graph.nodes.find((node) => node.id === edge.source);
        const targetNode = graph.nodes.find((node) => node.id === edge.target);
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
    [graph.edges, graph.nodes],
  );

  useEffect(() => {
    void fitView({ padding: 0.2 });
  }, [fitView, graph.nodes]);

  return (
    <div className="relative h-56">
      <FitButton />
      <ReactFlow
        className="monitoring-flow"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        fitView
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={1.4}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function RunGraph({ graph, steps }: { graph: GraphSnapshot; steps?: RunStep[] }) {
  return (
    <ReactFlowProvider>
      <Inner graph={graph} steps={steps} />
    </ReactFlowProvider>
  );
}
