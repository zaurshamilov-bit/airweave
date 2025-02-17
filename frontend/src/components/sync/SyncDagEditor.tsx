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
  Edge as FlowEdge,
} from "reactflow";
import "reactflow/dist/style.css";
import { useToast } from "@/components/ui/use-toast";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Save } from "lucide-react";
import { SourceNode } from "./nodes/SourceNode";
import { DestinationNode } from "./nodes/DestinationNode";
import { TransformerNode } from "./nodes/TransformerNode";
import { EntityNode } from "./nodes/EntityNode";

// Define custom node types
const nodeTypes: NodeTypes = {
  source: SourceNode,
  destination: DestinationNode,
  transformer: TransformerNode,
  entity: EntityNode,
};

interface SyncDagEditorProps {
  syncId: string;
  initialDag?: {
    nodes: Node[];
    edges: Edge[];
  };
  onSave?: () => void;
}

interface DagUpdateRequest {
  name: string;
  description: string;
  sync_id: string;
  nodes: {
    id: string;
    type: string;
    name: string;
    config?: Record<string, any>;
    source_id?: string;
    destination_id?: string;
    transformer_id?: string;
    entity_definition_id?: string;
  }[];
  edges: {
    from_node_id: string;
    to_node_id: string;
  }[];
}

export const SyncDagEditor = ({ syncId, initialDag, onSave }: SyncDagEditorProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialDag?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialDag?.edges || []);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Load initial DAG if not provided
  useEffect(() => {
    const loadDag = async () => {
      if (initialDag) return;
      try {
        const resp = await apiClient.get(`/sync/${syncId}/dag`);
        if (!resp.ok) throw new Error("Failed to load DAG");
        const data = await resp.json();
        
        // Convert backend data to React Flow format and assign positions
        const flowNodes = data.nodes.map((node: any, index: number) => {
          let position = { x: 0, y: 0 };
          
          // Assign positions based on node type
          switch (node.type.toLowerCase()) {
            case "source":
              position = { x: 100, y: 100 };
              break;
            case "entity":
              // Distribute entity nodes vertically in the middle
              const entityCount = data.nodes.filter((n: any) => n.type.toLowerCase() === "entity").length;
              const ySpacing = 400 / (entityCount + 1);
              const entityIndex = data.nodes.filter(
                (n: any, i: number) => n.type.toLowerCase() === "entity" && i < index
              ).length;
              position = { x: 400, y: ySpacing * (entityIndex + 1) };
              break;
            case "destination":
              position = { x: 700, y: 100 };
              break;
            default:
              position = { x: 250 * (index + 1), y: 100 };
          }

          return {
            id: node.id,
            type: node.type.toLowerCase(),
            position,
            data: {
              name: node.name,
              config: node.config,
              sourceId: node.source_id,
              destinationId: node.destination_id,
              transformerId: node.transformer_id,
              entityDefinitionId: node.entity_definition_id,
            },
          };
        });

        const flowEdges = data.edges.map((edge: any) => ({
          id: edge.id,
          source: edge.from_node_id,
          target: edge.to_node_id,
        }));

        setNodes(flowNodes);
        setEdges(flowEdges);
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

  // Handle connecting nodes
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges]
  );

  // Handle saving the DAG
  const handleSave = async () => {
    setIsLoading(true);
    try {
      // Convert React Flow data to backend format (omit position data)
      const dagData: DagUpdateRequest = {
        name: "DAG from UI",
        description: "Created via DAG editor",
        sync_id: syncId,
        nodes: nodes.map((node) => ({
          id: node.id,
          type: node.type?.toUpperCase() || "",
          name: node.data.name,
          config: node.data.config,
          source_id: node.data.sourceId,
          destination_id: node.data.destinationId,
          transformer_id: node.data.transformerId,
          entity_definition_id: node.data.entityDefinitionId,
        })),
        edges: edges.map((edge) => ({
          from_node_id: edge.source,
          to_node_id: edge.target,
        })),
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
        fitView
        className="bg-background"
      >
        <Background />
        <Controls />
        <Panel position="top-right" className="bg-background/50 p-2 rounded-lg">
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