import { useCallback, useEffect, useState } from "react";
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

// Define custom node types
const nodeTypes: NodeTypes = {
  source: SourceNode,
  destination: DestinationNode,
  entity: EntityNode,
};

const edgeTypes = {
  button: ButtonEdge,
};

interface SyncDagEditorProps {
  syncId: string;
  initialDag?: DagDefinition;
  onSave?: () => void;
}

const getLayoutedElements = (nodes: FlowNode[], edges: FlowEdge[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({ rankdir: direction });

  // Node width and height for layout calculation
  const nodeWidth = 180;
  const nodeHeight = 60;

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

  // Get positioned nodes
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    };
  });

  return { nodes: layoutedNodes, edges };
};

export const SyncDagEditor = ({ syncId, initialDag, onSave }: SyncDagEditorProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Load initial DAG
  useEffect(() => {
    const loadDag = async () => {
      try {
        // If we have initial DAG data, use it
        if (initialDag) {
          const flowNodes = toFlowNodes(initialDag.nodes);
          setNodes(flowNodes);
          
          // Create edges with correct source/target properties
          initialDag.edges.forEach(edge => {
            const connection = {
              source: edge.from_node_id,
              target: edge.to_node_id,
              type: 'button',
              id: edge.id
            };
            setEdges((eds) => addEdge(connection, eds));
          });
          return;
        }

        // Otherwise fetch from API
        const resp = await apiClient.get(`/sync/${syncId}/dag`);
        if (!resp.ok) throw new Error("Failed to load DAG");
        const data: DagDefinition = await resp.json();
        
        const flowNodes = toFlowNodes(data.nodes);
        setNodes(flowNodes);
        
        // Create edges with correct source/target properties
        data.edges.forEach(edge => {
          const connection = {
            source: edge.from_node_id,
            target: edge.to_node_id,
            type: 'button',
            id: edge.id
          };
          setEdges((eds) => addEdge(connection, eds));
        });
      } catch (err: any) {
        toast({
          variant: "destructive",
          title: "Failed to load DAG",
          description: err.message || String(err),
        });
      }
    };

    loadDag();
  }, [initialDag, syncId, setNodes, setEdges, toast]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

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
        edges={edges}
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
            onClick={() => {
              const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                nodes,
                edges,
                'TB'
              );
              setNodes(layoutedNodes);
              setEdges(layoutedEdges);
            }}
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