import { useEffect, useMemo, useRef } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
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

function Canvas({ id, layoutWidth }: { id: string; layoutWidth: number }) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { fitView } = useReactFlow();
  const ready = useNodesInitialized();
  const paneRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    const pane = paneRef.current;
    if (!pane || !ready) return;
    let frame = 0;
    const fit = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        if (pane.clientWidth < 24 || pane.clientHeight < 24) return;
        void fitView();
      });
    };
    const observer = new ResizeObserver(fit);
    observer.observe(pane);
    fit();
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [fitView, layoutWidth, ready]);

  if (query.isLoading) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.detail.graphLoading')}</p>;
  }
  if (query.isError || !document) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.error.missing')}</p>;
  }

  return (
    <div ref={paneRef} className="h-full min-h-64 w-full min-w-0 overflow-hidden">
      <ReactFlow
        className="network-flow h-full w-full bg-background"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={(changes) => {
          if (changes.some((change) => change.type === 'dimensions')) {
            void fitView();
          }
        }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        panOnScroll
        zoomOnPinch
        zoomOnScroll
        fitView
        colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
        proOptions={{ hideAttribution: true }}
        deleteKeyCode={[]}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function ReadonlyGraph({ id, layoutWidth = 0 }: { id: string; layoutWidth?: number }) {
  return (
    <ReactFlowProvider key={id}>
      <Canvas id={id} layoutWidth={layoutWidth} />
    </ReactFlowProvider>
  );
}
