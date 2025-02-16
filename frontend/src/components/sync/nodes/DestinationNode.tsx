import { HardDrive } from "lucide-react";
import { BaseNode } from "./BaseNode";

export const DestinationNode = (props: any) => {
  return (
    <BaseNode
      {...props}
      hasOutputs={false}
      icon={<HardDrive className="w-4 h-4 text-green-500" />}
      className="bg-green-50 dark:bg-green-950"
    />
  );
}; 