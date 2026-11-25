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
import { cn } from '@/lib/utils';
import { useEditorNetworkQuery } from '@/modules/network/api';
import type { AgentNetworkDocument, ValidationIssue } from '@/modules/network/model/document';
import { NetworkNode, type NetworkNodeData } from '@/modules/network/canvas/NetworkNode';
import { connectedPortKeys, toRfHandlePair } from '@/modules/network/canvas/handles';
import { asPortContext } from '@/modules/network/schema/ports';

const nodeTypes = { network: NetworkNode };

/** How a node differs from the network read in: new or changed (netz-architekt 7.3). */
export type NodeMark = 'added' | 'changed';

const MARK_CLASS: Record<NodeMark, string> = {
  added: 'rounded-lg ring-2 ring-primary ring-offset-2 ring-offset-background',
  changed: 'rounded-lg ring-2 ring-warning ring-offset-2 ring-offset-background',
};

/** A network document as a graph that cannot be edited; issues mark their nodes. */
function DocumentCanvas({
  document,
  layoutWidth,
  issues,
  marks,
}: {
  document: AgentNetworkDocument;
  layoutWidth: number;
  issues?: ValidationIssue[];
  marks?: Record<string, NodeMark>;
}) {
  const { resolvedTheme } = useTheme();
  const { fitView } = useReactFlow();
  const ready = useNodesInitialized();
  const paneRef = useRef<HTMLDivElement>(null);
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
      className: cn('overflow-visible', marks?.[node.id] ? MARK_CLASS[marks[node.id]] : undefined),
      data: {
        graph: node,
        issues: (issues ?? []).filter((issue) => issue.nodeId === node.id),
        readOnly: true,
        connected: connectedPortKeys(node.id, document.edges),
        portContext,
      } satisfies NetworkNodeData,
    }));
  }, [document, portContext, issues, marks]);
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
  }, [fitView, layoutWidth, ready, document]);

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
        zoomOnScroll={false}
        panOnScroll={false}
        zoomOnPinch
        preventScrolling={false}
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

function StoredCanvas({ id, layoutWidth }: { id: string; layoutWidth: number }) {
  const { t } = useTranslation();
  const query = useEditorNetworkQuery(id);
  if (query.isLoading) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.detail.graphLoading')}</p>;
  }
  if (query.isError || !query.data) {
    return <p className="p-3 text-sm text-muted-foreground">{t('networks.error.missing')}</p>;
  }
  return <DocumentCanvas document={query.data} layoutWidth={layoutWidth} />;
}

export function ReadonlyGraph({ id, layoutWidth = 0 }: { id: string; layoutWidth?: number }) {
  return (
    <ReactFlowProvider key={id}>
      <StoredCanvas id={id} layoutWidth={layoutWidth} />
    </ReactFlowProvider>
  );
}

/** A document that is not stored (the architect's draft). */
export function DocumentGraph({
  document,
  layoutWidth = 0,
  issues,
  marks,
}: {
  document: AgentNetworkDocument;
  layoutWidth?: number;
  issues?: ValidationIssue[];
  marks?: Record<string, NodeMark>;
}) {
  return (
    <ReactFlowProvider>
      <DocumentCanvas document={document} layoutWidth={layoutWidth} issues={issues} marks={marks} />
    </ReactFlowProvider>
  );
}
