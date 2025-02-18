import { memo } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { Box } from "lucide-react";
import { cn } from "@/lib/utils";

interface EntityNodeData {
  name: string;
  entityDefinitionId: string;
  config?: Record<string, any>;
}

interface EntityNodeProps {
  data: EntityNodeData;
}

export const EntityNode = memo(({ data, selected, ...props }: NodeProps) => {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={cn(
          "w-10 h-10 flex items-center justify-center rounded-2xl bg-muted/40 backdrop-blur-sm",
          "transition-colors duration-200",
          selected ? "bg-muted/90" : "bg-muted/80"
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="opacity-0 w-0 h-0"
          style={{ left: -6 }}
        />
        <Box className="w-6 h-6 text-muted-foreground" />
        <Handle
          type="source"
          position={Position.Right}
          className="opacity-0 w-0 h-0"
          style={{ right: -6 }}
        />
      </div>
      <span className="text-sm font-light text-foreground max-w-[120px] text-center truncate">{data.name}</span>
    </div>
  );
});

EntityNode.displayName = "EntityNode"; 