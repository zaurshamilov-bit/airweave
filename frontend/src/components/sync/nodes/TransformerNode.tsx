import { memo } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { SplitSquareHorizontal, Wand2 } from "lucide-react";

const getTransformerIcon = (transformerId: string) => {
  switch (transformerId) {
    case 'text-splitter':
      return <SplitSquareHorizontal className="w-8 h-8" />;
    default:
      return <Wand2 className="w-8 h-8" />;
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
      variant="square"
    />
  );
});

TransformerNode.displayName = "TransformerNode"; 