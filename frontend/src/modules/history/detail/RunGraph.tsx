import { useMemo } from 'react';
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
import { StatusNode, statusNodeSize, type StatusFlowNode } from '@/modules/monitoring/graph/StatusNode';
import { useFitGraph } from '@/modules/monitoring/graph/useFitGraph';
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
        const size = statusNodeSize(node.type, node.data, node.id);
        return {
          id: node.id,
          type: 'status',
          position: node.position,
          className: 'overflow-visible',
          width: size.width,
          height: size.height,
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

  const paneRef = useFitGraph(
    graph.nodes.map((node) => node.id).join(','),
    nodes.length,
  );

  return (
    <div ref={paneRef} className="relative h-56">
      <FitButton />
      <ReactFlow
        className="monitoring-flow h-full w-full"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        fitView
        fitViewOptions={{ padding: 0.2 }}
        onInit={(instance) => {
          void instance.fitView({ padding: 0.2, duration: 0 });
        }}
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
