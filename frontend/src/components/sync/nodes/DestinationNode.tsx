import { memo, useEffect, useState } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";
import { Connection } from "@/components/sync/dag";
import { cn } from "@/lib/utils";
import { toast } from "@/components/ui/use-toast";

export const DestinationNode = memo(({ data, selected, ...props }: NodeProps) => {
  const [connection, setConnection] = useState<Connection | null>(null);

  useEffect(() => {
    const fetchConnection = async () => {
      if (!data.connection_id) return;

      try {
        const resp = await apiClient.get(`/connections/detail/${data.connection_id}`);
        if (!resp.ok) throw new Error("Failed to fetch connection details");
        const connData = await resp.json();
        setConnection(connData);
      } catch (error) {
        console.error("Error fetching connection:", error);
        toast({
          variant: "destructive",
          title: "Failed to load connection details",
          description: "Please try refreshing the page",
        });
      }
    };

    fetchConnection();
  }, [data.connection_id]);

  // Use qdrant_native as default shortName when no connection
  const shortName = connection?.short_name || (data.connection_id ? data.shortName : "qdrant");
  const name = connection?.name || data.name || "Native Qdrant";

  return (
    <div className="w-10 h-10">
      <div
        className={cn(
          "w-full h-full flex flex-col bg-background/80 backdrop-blur-sm",
          "border-[1px] transition-colors duration-200 cursor-pointer",
          "border-muted-foreground/50 hover:border-primary rounded-lg",
          selected ? "border-primary shadow-sm shadow-primary/20" : ""
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="w-1 h-1 ml-[1px] border border-background bg-muted-foreground"
        />

        <div className="w-full h-full flex items-center justify-center">
          <div className="flex items-center justify-center p-2">
            <img
              src={getDestinationIconUrl("qdrant")}
              alt="Native Qdrant"
              className="max-w-full max-h-full w-auto h-auto object-contain"
            />
          </div>
        </div>
      </div>
      <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-[8px] text-foreground text-center">Qdrant</span>
      </div>
    </div>
  );
});

DestinationNode.displayName = "DestinationNode";
