import { Handle, Position } from "reactflow";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Box } from "lucide-react";

interface EntityNodeData {
  name: string;
  entityDefinitionId: string;
  config?: Record<string, any>;
}

interface EntityNodeProps {
  data: EntityNodeData;
}

export const EntityNode = ({ data }: EntityNodeProps) => {
  return (
    <Card className="w-[200px] bg-background border-primary/20">
      <CardHeader className="p-4">
        <div className="flex items-center space-x-2">
          <Box className="w-4 h-4 text-primary" />
          <CardTitle className="text-sm font-medium">{data.name}</CardTitle>
        </div>
      </CardHeader>
      <Handle type="target" position={Position.Left} className="w-2 h-2 bg-primary" />
      <Handle type="source" position={Position.Right} className="w-2 h-2 bg-primary" />
    </Card>
  );
}; 