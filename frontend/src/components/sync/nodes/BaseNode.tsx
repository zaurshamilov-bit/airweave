import { memo } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { cn } from "@/lib/utils";

interface BaseNodeProps extends NodeProps {
  icon: React.ReactNode;
  label: string;
  handles?: {
    source?: boolean;
    target?: boolean;
  };
  variant?: 'square' | 'card';
}

export const BaseNode = memo(({ 
  icon, 
  label, 
  handles = { source: true, target: true }, 
  selected,
  variant = 'card'
}: BaseNodeProps) => {
  if (variant === 'square') {
    return (
      <div className="flex flex-col items-center gap-1.5">
        <div
          className={cn(
            "w-20 h-20 flex items-center justify-center rounded-lg shadow-md bg-background/80 backdrop-blur-sm",
            "border-2 transition-colors duration-200",
            selected ? "border-primary" : "border-border"
          )}
        >
          {handles?.target && (
            <Handle
              type="target"
              position={Position.Left}
              className="w-2 h-2 -ml-[2px] border border-background bg-muted-foreground"
            />
          )}
          <div className="w-10 h-10 flex items-center justify-center">
            {icon}
          </div>
          {handles?.source && (
            <Handle
              type="source"
              position={Position.Right}
              className="w-2 h-2 -mr-[2px] border border-background bg-muted-foreground"
            />
          )}
        </div>
        <span className="text-sm font-semibold text-foreground max-w-[120px] text-center truncate">{label}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "px-4 py-2 shadow-md rounded-md bg-background border-2 min-w-[150px]",
        selected ? "border-primary" : "border-border"
      )}
    >
      {handles?.target && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-3 h-3 border-2 border-background bg-muted-foreground"
        />
      )}
      <div className="flex items-center gap-2">
        <div className="w-10 h-10 flex items-center justify-center rounded-full bg-muted">
          {icon}
        </div>
        <span className="text-sm font-medium">{label}</span>
      </div>
      {handles?.source && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-3 h-3 border-2 border-background bg-muted-foreground"
        />
      )}
    </div>
  );
});

BaseNode.displayName = "BaseNode"; 