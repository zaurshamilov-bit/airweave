import { Box } from "lucide-react";
import { BaseNode } from "./BaseNode";

export const EntityNode = (props: any) => {
  return (
    <BaseNode
      {...props}
      icon={<Box className="w-4 h-4 text-orange-500" />}
      className="bg-orange-50 dark:bg-orange-950"
    />
  );
}; 