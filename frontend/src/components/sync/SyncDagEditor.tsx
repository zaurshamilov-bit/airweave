import { useCallback, useEffect, useState, useRef } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  NodeTypes,
  addEdge,
  useEdgesState,
  useNodesState,
  Panel,
  Connection,
  ConnectionMode,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import { useToast } from "@/components/ui/use-toast";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LayoutGrid, Save } from "lucide-react";
import { SourceNode } from "./nodes/SourceNode";
import { DestinationNode } from "./nodes/DestinationNode";
import { EntityNode } from "./nodes/EntityNode";
import { ButtonEdge } from "./edges/ButtonEdge";
import dagre from "dagre";
import { 
  DagDefinition, 
  FlowNode, 
  FlowEdge,
  toFlowNodes,
  toFlowEdges,
  toDagNodes,
  toDagEdges,
} from "@/components/sync/dag";
import { TransformerNode } from "./nodes/TransformerNode";

// Define custom node types
const nodeTypes: NodeTypes = {
  source: SourceNode,
  destination: DestinationNode,
  entity: EntityNode,
  transformer: TransformerNode,
};

const edgeTypes = {
  button: ButtonEdge,
};

interface SyncDagEditorProps {
  syncId: string;
  initialDag?: DagDefinition;
  onSave?: () => void;
}

const nodeWidth = 200;
const nodeHeight = 50;

const getLayoutedElements = (nodes: FlowNode[], edges: FlowEdge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({ 
    rankdir: 'LR',
    nodesep: 80,
    ranksep: 200,
    align: 'DL',
    marginx: 50,
    marginy: 50,
  });

  // Add nodes to dagre
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  // Add edges to dagre
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Calculate layout
  dagre.layout(dagreGraph);

  // First pass: get all positions
  const positions = new Map();
  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    positions.set(node.id, {
      x: nodeWithPosition.x,
      y: nodeWithPosition.y
    });
  });

  // For source and destination nodes, calculate the center position based on their connected nodes
  const layoutedNodes = nodes.map((node) => {
    const pos = positions.get(node.id);
    let finalY = pos.y;

    if (node.type === 'source') {
      // Find all nodes this source connects to
      const targetNodes = edges
        .filter(edge => edge.source === node.id)
        .map(edge => positions.get(edge.target)?.y)
        .filter(y => y !== undefined);

      if (targetNodes.length > 0) {
        finalY = targetNodes.reduce((sum, y) => sum + y, 0) / targetNodes.length;
      }
    } else if (node.type === 'destination') {
      // Find all nodes that connect to this destination
      const sourceNodes = edges
        .filter(edge => edge.target === node.id)
        .map(edge => positions.get(edge.source)?.y)
        .filter(y => y !== undefined);

      if (sourceNodes.length > 0) {
        finalY = sourceNodes.reduce((sum, y) => sum + y, 0) / sourceNodes.length;
      }
    }

    return {
      ...node,
      targetPosition: 'left',
      sourcePosition: 'right',
      position: {
        x: pos.x - nodeWidth / 2,
        y: finalY - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

const SyncDagEditorInner = ({ syncId, initialDag, onSave }: SyncDagEditorProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();
  const { fitView, addNodes, addEdges } = useReactFlow();
  const isInitialLoad = useRef(true);

  const applyLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(nodes as FlowNode[], edges as FlowEdge[]);
    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);
    fitView({ padding: 0.2 });
  }, [nodes, edges, setNodes, setEdges, fitView]);

  // Apply layout when nodes or edges change (except during initial load)
  useEffect(() => {
    if (!isInitialLoad.current && nodes.length > 0) {
      const timeoutId = setTimeout(() => {
        applyLayout();
      }, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [nodes.length, edges.length]);

  // Load initial DAG
  useEffect(() => {
    const loadDag = async () => {
      try {
        isInitialLoad.current = true;
        
        // If we have initial DAG data, use it
        if (initialDag) {
          const flowNodes = toFlowNodes(initialDag.nodes);
          const initialEdges = initialDag.edges.map(edge => ({
            source: edge.from_node_id,
            target: edge.to_node_id,
            type: 'button' as const,
            id: edge.id
          }));

          setNodes(flowNodes as Node[]);
          setEdges(initialEdges as Edge[]);
          
          // Apply initial layout
          const { nodes: layoutedNodes } = getLayoutedElements(flowNodes, initialEdges);
          setNodes([...layoutedNodes] as Node[]);
          
          fitView({ padding: 0.2 });
          return;
        }

        // Otherwise fetch from API
        const resp = await apiClient.get(`/sync/${syncId}/dag`);
        if (!resp.ok) throw new Error("Failed to load DAG");
        const data: DagDefinition = await resp.json();
        
        const flowNodes = toFlowNodes(data.nodes);
        const initialEdges = data.edges.map(edge => ({
          source: edge.from_node_id,
          target: edge.to_node_id,
          type: 'button' as const,
          id: edge.id
        }));

        setNodes(flowNodes as Node[]);
        setEdges(initialEdges as Edge[]);
        
        // Apply initial layout
        const { nodes: layoutedNodes } = getLayoutedElements(flowNodes, initialEdges);
        setNodes([...layoutedNodes] as Node[]);
        
        fitView({ padding: 0.2 });
      } catch (err: any) {
        toast({
          variant: "destructive",
          title: "Failed to load DAG",
          description: err.message || String(err),
        });
      } finally {
        isInitialLoad.current = false;
      }
    };

    loadDag();
  }, [initialDag, syncId, setNodes, setEdges, toast, fitView]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Add this new function to handle transformer creation
  const handleTransformerAdd = useCallback((
    transformerId: string,
    transformerName: string,
    sourceNodeId: string,
    targetNodeId: string,
    sourceEdge: Edge
  ) => {
    // Disable layout updates temporarily
    isInitialLoad.current = true;

    // Create transformer node
    const transformerNode: Node = {
      id: `transformer-${Date.now()}`,
      type: 'transformer',
      data: {
        name: transformerName,
        transformer_id: transformerId,
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    // Create chunk nodes
    const chunk1: Node = {
      id: `chunk-${Date.now()}-1`,
      type: 'entity',
      data: {
        name: 'Chunk 1',
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    const chunk2: Node = {
      id: `chunk-${Date.now()}-2`,
      type: 'entity',
      data: {
        name: 'Chunk 2',
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    };

    // Create new edges
    const newEdges: Edge[] = [
      // Edge from source to transformer
      {
        id: `edge-${Date.now()}-1`,
        source: sourceNodeId,
        target: transformerNode.id,
        type: 'button',
      },
      // Edges from transformer to chunks
      {
        id: `edge-${Date.now()}-2`,
        source: transformerNode.id,
        target: chunk1.id,
        type: 'button',
      },
      {
        id: `edge-${Date.now()}-3`,
        source: transformerNode.id,
        target: chunk2.id,
        type: 'button',
      },
      // Edges from chunks to target
      {
        id: `edge-${Date.now()}-4`,
        source: chunk1.id,
        target: targetNodeId,
        type: 'button',
      },
      {
        id: `edge-${Date.now()}-5`,
        source: chunk2.id,
        target: targetNodeId,
        type: 'button',
      },
    ];

    // Update all state at once
    const updatedEdges = edges.filter(e => e.id !== sourceEdge.id).concat(newEdges);
    const updatedNodes = [...nodes, transformerNode, chunk1, chunk2];
    
    // Calculate new layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      updatedNodes as FlowNode[],
      updatedEdges as FlowEdge[]
    );

    // Apply all updates at once
    setNodes([...layoutedNodes] as Node[]);
    setEdges([...layoutedEdges] as Edge[]);

    // Re-enable layout updates and fit view
    setTimeout(() => {
      isInitialLoad.current = false;
      fitView({ padding: 0.2 });
    }, 50);
  }, [nodes, edges, setNodes, setEdges, fitView]);

  // Handle saving the DAG
  const handleSave = async () => {
    setIsLoading(true);
    try {
      const dagData: DagDefinition = {
        id: initialDag?.id || '',
        name: initialDag?.name || "DAG from UI",
        description: initialDag?.description || "Created via DAG editor",
        syncId: syncId,
        nodes: toDagNodes(nodes),
        edges: toDagEdges(edges),
      };

      const resp = await apiClient.put(`/sync/${syncId}/dag`, dagData);
      if (!resp.ok) throw new Error("Failed to save DAG");

      toast({
        title: "DAG saved successfully",
      });

      onSave?.();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Failed to save DAG",
        description: err.message || String(err),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full h-[600px] relative border rounded-lg bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges.map(edge => ({
          ...edge,
          data: { onTransformerAdd: handleTransformerAdd }
        }))}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        className="bg-background"
        defaultEdgeOptions={{
          type: 'button',
        }}
      >
        <Background />
        <Controls />
        <Panel position="top-right" className="bg-background/50 p-2 rounded-lg flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={applyLayout}
          >
            <LayoutGrid className="w-4 h-4 mr-2" />
            Layout
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleSave}
            disabled={isLoading}
          >
            <Save className="w-4 h-4 mr-2" />
            Save DAG
          </Button>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export const SyncDagEditor = (props: SyncDagEditorProps) => (
  <ReactFlowProvider>
    <SyncDagEditorInner {...props} />
  </ReactFlowProvider>
); 