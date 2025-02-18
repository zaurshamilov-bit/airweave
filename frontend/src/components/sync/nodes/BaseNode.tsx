import { memo } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { cn } from "@/lib/utils";
import React from "react";

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
      <div className="w-10 h-10">
        <div
          className={cn(
            "w-full h-full flex items-center justify-center rounded-lg shadow-md bg-background/80 backdrop-blur-sm",
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
          <div className="w-8 h-8 flex items-center justify-center">
            {React.cloneElement(icon as React.ReactElement, {
              className: 'w-6 h-6'
            })}
          </div>
          {handles?.source && (
            <Handle
              type="source"
              position={Position.Right}
              className="w-2 h-2 -mr-[2px] border border-background bg-muted-foreground"
            />
          )}
        </div>
        <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="text-sm font-semibold text-foreground text-center">{label}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-w-[150px]">
      <div
        className={cn(
          "px-4 py-2 shadow-md rounded-md bg-background border-2",
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
    </div>
  );
});

BaseNode.displayName = "BaseNode"; 