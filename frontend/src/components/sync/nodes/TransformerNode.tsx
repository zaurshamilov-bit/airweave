import { Cog } from "lucide-react";
import { BaseNode } from "./BaseNode";

export const TransformerNode = (props: any) => {
  return (
    <BaseNode
      {...props}
      icon={<Cog className="w-4 h-4 text-purple-500" />}
      className="bg-purple-50 dark:bg-purple-950"
    />
  );
}; 