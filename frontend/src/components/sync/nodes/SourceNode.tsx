import { Handle, Position } from "reactflow";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Database } from "lucide-react";

interface SourceNodeData {
  name: string;
  sourceId: string;
  config?: Record<string, any>;
}

interface SourceNodeProps {
  data: SourceNodeData;
}

export const SourceNode = ({ data }: SourceNodeProps) => {
  return (
    <Card className="w-[200px] bg-background border-primary/20">
      <CardHeader className="p-4">
        <div className="flex items-center space-x-2">
          <Database className="w-4 h-4 text-primary" />
          <CardTitle className="text-sm font-medium">{data.name}</CardTitle>
        </div>
      </CardHeader>
      <Handle type="source" position={Position.Right} className="w-2 h-2 bg-primary" />
    </Card>
  );
}; 