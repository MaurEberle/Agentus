import { useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from '@xyflow/react';
import { useTheme } from 'next-themes';
import { useTranslation } from 'react-i18next';
import { useEditorNetworkQuery } from '@/modules/network/api';
import { NetworkNode, type NetworkNodeData } from '@/modules/network/canvas/NetworkNode';
import { connectedPortKeys, toRfHandlePair } from '@/modules/network/canvas/handles';
import { asPortContext } from '@/modules/network/schema/ports';

const nodeTypes = { network: NetworkNode };

function Canvas({ id }: { id: string }) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const query = useEditorNetworkQuery(id);
  const document = query.data;
  const portContext = useMemo(
    () => (document ? asPortContext(document.nodes, document.edges) : undefined),
    [document],
  );
  const nodes = useMemo<Node[]>(() => {
    if (!document || !portContext) return [];
    return document.nodes.map((node) => ({
      id: node.id,
      type: 'network',
      position: node.position,
      draggable: false,
      selectable: false,
      className: 'overflow-visible',
      data: {
        graph: node,
        issues: [],
        readOnly: true,
        connected: connectedPortKeys(node.id, document.edges),
        portContext,
      } satisfies NetworkNodeData,
    }));
  }, [document, portContext]);
  const edges = useMemo<Edge[]>(() => {
    if (!document || !portContext) return [];
    return document.edges.map((edge) => {
      const sourceNode = document.nodes.find((node) => node.id === edge.source);
      const targetNode = document.nodes.find((node) => node.id === edge.target);
      const handles = toRfHandlePair(sourceNode, targetNode, edge, portContext);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      };
    });
  }, [document, portContext]);

  if (query.isLoading) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.detail.graphLoading')}</p>;
  }
  if (query.isError || !document) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.error.missing')}</p>;
  }

  return (
    <ReactFlow
      className="network-flow h-full w-full bg-background"
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag
      panOnScroll
      zoomOnPinch
      zoomOnScroll
      fitView
      fitViewOptions={{ padding: 0.2 }}
      onInit={(instance) => {
        void instance.fitView({ padding: 0.2, duration: 0 });
      }}
      colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
      proOptions={{ hideAttribution: true }}
      deleteKeyCode={[]}
      minZoom={0.2}
      maxZoom={1.5}
    >
      <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function ReadonlyGraph({ id }: { id: string }) {
  return (
    <ReactFlowProvider key={id}>
      <div className="h-full min-h-64">
        <Canvas id={id} />
      </div>
    </ReactFlowProvider>
  );
}
