import { memo, useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";
import { Connection } from "@/components/sync/dag";
import { toast } from "@/components/ui/use-toast";

export const DestinationNode = memo(({ data, ...props }: NodeProps) => {
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

  // Use weaviate_native as default shortName when no connection
  const shortName = connection?.short_name || (data.connection_id ? data.shortName : "weaviate_native");
  const name = connection?.name || data.name || "Native Weaviate";

  return (
    <BaseNode
      {...props}
      data={data}
      icon={
        <img 
          src={getDestinationIconUrl(shortName)} 
          alt={name}
          className="w-6 h-6"
        />
      }
      label={name}
      handles={{ source: false, target: true }}
      variant="square"
    />
  );
});

DestinationNode.displayName = "DestinationNode"; 