import { memo } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { getDestinationIconUrl } from "@/lib/utils/icons";

export const DestinationNode = memo(({ data, ...props }: NodeProps) => {
  return (
    <BaseNode
      {...props}
      icon={
        <img 
          src={getDestinationIconUrl(data.shortName)} 
          alt={data.name}
          className="w-6 h-6"
        />
      }
      label={data.name}
      handles={{ source: false, target: true }}
    />
  );
});

DestinationNode.displayName = "DestinationNode"; 