import { memo } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { SplitSquareHorizontal, Wand2 } from "lucide-react";

const getTransformerIcon = (transformerId: string) => {
  switch (transformerId) {
    case 'text-splitter':
      return <SplitSquareHorizontal className="w-4 h-4" />;
    default:
      return <Wand2 className="w-4 h-4" />;
  }
};

export const TransformerNode = memo(({ data, ...props }: NodeProps) => {
  return (
    <BaseNode
      {...props}
      data={data}
      icon={getTransformerIcon(data.transformer_id)}
      label={data.name}
      handles={{ source: true, target: true }}
    />
  );
});

TransformerNode.displayName = "TransformerNode"; 