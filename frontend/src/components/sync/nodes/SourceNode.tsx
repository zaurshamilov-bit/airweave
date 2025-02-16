import { Database } from "lucide-react";
import { BaseNode } from "./BaseNode";

export const SourceNode = (props: any) => {
  return (
    <BaseNode
      {...props}
      hasInputs={false}
      icon={<Database className="w-4 h-4 text-blue-500" />}
      className="bg-blue-50 dark:bg-blue-950"
    />
  );
}; 