import { memo } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { Box } from "lucide-react";

interface EntityNodeData {
  name: string;
  entityDefinitionId: string;
  config?: Record<string, any>;
}

interface EntityNodeProps {
  data: EntityNodeData;
}

export const EntityNode = memo(({ data, ...props }: NodeProps) => {
  return (
    <BaseNode
      {...props}
      data={data}
      icon={<Box className="w-6 h-6" />}
      label={data.name}
    />
  );
});

EntityNode.displayName = "EntityNode"; 