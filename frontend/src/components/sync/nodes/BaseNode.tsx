import { Handle, Position } from "reactflow";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface BaseNodeProps {
  data: {
    name: string;
    config?: Record<string, any>;
  };
  selected?: boolean;
  className?: string;
  icon?: React.ReactNode;
  hasInputs?: boolean;
  hasOutputs?: boolean;
}

export const BaseNode = ({
  data,
  selected,
  className,
  icon,
  hasInputs = true,
  hasOutputs = true,
}: BaseNodeProps) => {
  return (
    <Card
      className={cn(
        "px-4 py-2 shadow-md rounded-lg border-2 min-w-[150px]",
        selected ? "border-primary" : "border-border",
        className
      )}
    >
      {hasInputs && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-2 h-2 !bg-muted-foreground"
        />
      )}
      <div className="flex items-center gap-2">
        {icon}
        <div className="text-sm font-medium">{data.name}</div>
      </div>
      {hasOutputs && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-2 h-2 !bg-muted-foreground"
        />
      )}
    </Card>
  );
}; 