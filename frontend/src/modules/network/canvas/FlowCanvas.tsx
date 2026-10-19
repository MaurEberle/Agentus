import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent as ReactPointerEvent } from 'react';
import {
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  BackgroundVariant,
  ConnectionLineType,
  Controls,
  MiniMap,
  MarkerType,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
  type OnEdgesChange,
  type OnNodesChange,
  useReactFlow,
} from '@xyflow/react';
import { useTheme } from 'next-themes';
import { useTranslation } from 'react-i18next';
import { bindChannelHandle, connectionAllowed, type PortContext } from '@/modules/network/schema/ports';
import { createNode } from '@/modules/network/schema/defaults';
import { issuesForNode, validateDocument } from '@/modules/network/validation/validate';
import { useMcpRecipesQuery, useMcpServersQuery } from '@/modules/settings/api';
import type { GraphEdge, NodeType } from '@/modules/network/model/document';
import { newId } from '@/modules/network/model/document';
import { CanvasContextMenu, type MenuState } from '@/modules/network/canvas/ContextMenu';
import { connectedPortKeys, docHandleId, toRfHandlePair } from '@/modules/network/canvas/handles';
import { NetworkNode } from '@/modules/network/canvas/NetworkNode';
import {
  editorAddNode,
  editorDeleteSelection,
  editorDuplicateSelection,
  useNetworkEditor,
} from '@/modules/network/store';

const nodeTypes = { network: NetworkNode };

export function FlowCanvas({
  readOnly,
  onRequestInsert,
  onOpenInspector,
}: {
  readOnly: boolean;
  onRequestInsert: (position: { x: number; y: number }) => void;
  onOpenInspector?: () => void;
}) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { screenToFlowPosition, fitView, getViewport } = useReactFlow();
  const document = useNetworkEditor((state) => state.document);
  const snap = useNetworkEditor((state) => state.snap);
  const showGrid = useNetworkEditor((state) => state.showGrid);
  const showMinimap = useNetworkEditor((state) => state.showMinimap);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const panePointer = useRef<{ x: number; y: number } | null>(null);
  const mcp = useMcpServersQuery();
  const mcpRecipes = useMcpRecipesQuery();

  const issues = useMemo(
    () =>
      validateDocument(document, {
        mcpServers: mcp.data?.items,
        mcpRecipes: mcpRecipes.data?.items,
        mcpReady: !mcp.isLoading,
      }),
    // Positions/viewport are ignored; structure and name drive validation.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- document fields listed
    [document.nodes, document.edges, document.name, mcp.data, mcp.isLoading, mcpRecipes.data],
  );
  const graphSig = useMemo(
    () =>
      document.nodes.map((node) => `${node.id}:${node.type}:${JSON.stringify(node.data)}:${node.position.x},${node.position.y}`).join('|') +
      '::' +
      document.edges.map((edge) => `${edge.id}:${edge.source}:${edge.target}:${edge.sourceHandle}:${edge.targetHandle}`).join('|'),
    [document.edges, document.nodes],
  );

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const portContext = useMemo<PortContext>(
    () => ({ nodes: document.nodes, edges: document.edges }),
    [document.edges, document.nodes],
  );

  useEffect(() => {
    const { selectedNodeIds, selectedEdgeIds } = useNetworkEditor.getState();
    const selectedNodes = new Set(selectedNodeIds);
    const selectedEdges = new Set(selectedEdgeIds);
    setNodes((current) => {
      const prior = new Map(current.map((node) => [node.id, node]));
      return document.nodes.map((node) => {
        const previous = prior.get(node.id);
        return {
          id: node.id,
          type: 'network',
          position: node.position,
          selected: selectedNodes.has(node.id),
          draggable: !readOnly,
          className: 'overflow-visible',
          measured: previous?.measured,
          data: {
            graph: node,
            issues: issuesForNode(issues, node.id),
            readOnly,
            connected: connectedPortKeys(node.id, document.edges),
            portContext,
          },
        };
      });
    });
    setEdges(
      document.edges.map((edge) => {
        const sourceNode = document.nodes.find((item) => item.id === edge.source);
        const targetNode = document.nodes.find((item) => item.id === edge.target);
        const handles = toRfHandlePair(sourceNode, targetNode, edge, portContext);
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
          type: 'default',
          selected: selectedEdges.has(edge.id),
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          className: issues.some((issue) => issue.edgeId === edge.id) ? '!stroke-destructive' : undefined,
        };
      }),
    );
  }, [graphSig, issues, portContext, readOnly, document.edges, document.nodes]);

  const isValidConnection = useCallback(
    (connection: Connection | Edge) => {
      const source = document.nodes.find((node) => node.id === connection.source);
      const target = document.nodes.find((node) => node.id === connection.target);
      if (!source || !target) return false;
      return connectionAllowed({
        source,
        target,
        sourceHandle: docHandleId(connection.sourceHandle),
        targetHandle: docHandleId(connection.targetHandle),
        context: portContext,
      });
    },
    [document.nodes, portContext],
  );

  const onConnect: OnConnect = useCallback(
    (connection) => {
      if (readOnly || !connection.source || !connection.target) return;
      if (!isValidConnection(connection)) return;
      const source = document.nodes.find((node) => node.id === connection.source);
      const target = document.nodes.find((node) => node.id === connection.target);
      let sourceHandle = docHandleId(connection.sourceHandle);
      const targetHandle = docHandleId(connection.targetHandle);
      if (source?.type === 'orchestrator' && target?.type === 'agent' && targetHandle === 'channel') {
        sourceHandle = bindChannelHandle(sourceHandle, target.id);
      }
      // Multiple tool/knowledge edges may share one agent handle.
      const edge: GraphEdge = {
        id: newId('e'),
        source: connection.source,
        sourceHandle,
        target: connection.target,
        targetHandle,
      };
      useNetworkEditor.getState().setEdges([...document.edges, edge]);
    },
    [document.edges, document.nodes, isValidConnection, readOnly],
  );

  const onNodesChange: OnNodesChange = useCallback((changes) => {
    setNodes((current) => applyNodeChanges(changes, current));
  }, []);

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      if (readOnly) return;
      const type = event.dataTransfer.getData('application/agentus-node') as NodeType;
      if (!type) return;
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      editorAddNode(createNode(type, position, snap));
    },
    [readOnly, screenToFlowPosition, snap],
  );

  const replaceSelection = useCallback((nodeIds: string[], edgeIds: string[]) => {
    const nodeSet = new Set(nodeIds);
    const edgeSet = new Set(edgeIds);
    setNodes((current) => {
      const changes = current
        .filter((node) => Boolean(node.selected) !== nodeSet.has(node.id))
        .map((node) => ({ id: node.id, type: 'select' as const, selected: nodeSet.has(node.id) }));
      return changes.length === 0 ? current : applyNodeChanges(changes, current);
    });
    setEdges((current) => {
      const changes = current
        .filter((edge) => Boolean(edge.selected) !== edgeSet.has(edge.id))
        .map((edge) => ({ id: edge.id, type: 'select' as const, selected: edgeSet.has(edge.id) }));
      return changes.length === 0 ? current : applyEdgeChanges(changes, current);
    });
    useNetworkEditor.getState().select(nodeIds, edgeIds);
  }, []);

  const empty = document.nodes.length === 0;

  const clearPaneSelection = (event: ReactPointerEvent<HTMLDivElement>) => {
    const start = panePointer.current;
    panePointer.current = null;
    if (!start || event.button !== 0) return;
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (
      target.closest(
        '.react-flow__node, .react-flow__edge, .react-flow__handle, .react-flow__controls, .react-flow__minimap, .react-flow__panel, .react-flow__attribution',
      )
    ) {
      return;
    }
    if (!target.closest('.react-flow__pane')) return;
    if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) return;
    replaceSelection([], []);
  };

  return (
    <div
      className="relative h-full min-h-0 w-full"
      onPointerDown={(event) => {
        panePointer.current = { x: event.clientX, y: event.clientY };
      }}
      onPointerUp={clearPaneSelection}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onNodeDragStop={(_event, _node, all) => {
          if (readOnly) return;
          useNetworkEditor.getState().setNodes(
            document.nodes.map((node) => {
              const live = all.find((item) => item.id === node.id);
              return live ? { ...node, position: live.position } : node;
            }),
          );
        }}
        onSelectionChange={({ nodes: selNodes, edges: selEdges }) => {
          useNetworkEditor.getState().select(
            selNodes.map((node) => node.id),
            selEdges.map((edge) => edge.id),
          );
        }}
        onNodeClick={(event, node) => {
          if (event.shiftKey) return;
          replaceSelection([node.id], []);
        }}
        onPaneClick={() => replaceSelection([], [])}
        onPaneContextMenu={(event) => {
          event.preventDefault();
          setMenu({kind: 'pane', x: event.clientX, y: event.clientY, flow: screenToFlowPosition({ x: event.clientX, y: event.clientY })});
        }}
        onNodeDoubleClick={() => {
          onOpenInspector?.();
        }}
        onNodeContextMenu={(event, node) => {
          event.preventDefault();
          replaceSelection([node.id], []);
          setMenu({ kind: 'node', x: event.clientX, y: event.clientY, id: node.id });
        }}
        onEdgeContextMenu={(event, edge) => {
          event.preventDefault();
          replaceSelection([], [edge.id]);
          setMenu({ kind: 'edge', x: event.clientX, y: event.clientY, id: edge.id });
        }}
        onMoveEnd={() => useNetworkEditor.getState().setViewport(getViewport())}
        onDragOver={(event) => {
          event.preventDefault();
          event.dataTransfer.dropEffect = 'move';
        }}
        onDrop={onDrop}
        snapToGrid={snap}
        snapGrid={[16, 16]}
        connectionLineType={ConnectionLineType.Bezier}
        fitView={false}
        deleteKeyCode={[]}
        multiSelectionKeyCode="Shift"
        selectionOnDrag
        paneClickDistance={8}
        panOnDrag={[1]}
        panOnScroll
        zoomOnPinch
        colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
        proOptions={{ hideAttribution: true }}
        className="network-flow h-full bg-background"
      >
        {showGrid ? <Background variant={BackgroundVariant.Dots} gap={16} size={1} /> : null}
        <Controls showInteractive={!readOnly} />
        {showMinimap ? <MiniMap pannable zoomable /> : null}
      </ReactFlow>
      {empty ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
          <p className="max-w-xs rounded-md bg-background/80 px-3 py-1.5 text-center text-sm text-muted-foreground">
            {t('network.empty.body')}
          </p>
        </div>
      ) : null}
      {menu ? (
        <CanvasContextMenu
          menu={menu}
          onClose={() => setMenu(null)}
          onInsert={(flow) => {
            onRequestInsert(flow);
            setMenu(null);
          }}
          onFit={() => {
            fitView({ padding: 0.2 });
            setMenu(null);
          }}
          onDuplicate={() => {
            editorDuplicateSelection();
            setMenu(null);
          }}
          onDelete={() => {
            editorDeleteSelection();
            setMenu(null);
          }}
        />
      ) : null}
    </div>
  );
}
