import { memo } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { getAppIconUrl } from "@/lib/utils/icons";

export const SourceNode = memo(({ data, ...props }: NodeProps) => {
  return (
    <BaseNode
      {...props}
      icon={
        <img 
          src={getAppIconUrl(data.shortName)} 
          alt={data.name}
          className="w-6 h-6"
        />
      }
      label={data.name}
      handles={{ source: true, target: false }}
    />
  );
});

SourceNode.displayName = "SourceNode"; 