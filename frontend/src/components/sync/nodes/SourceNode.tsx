import { memo, useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { BaseNode } from "./BaseNode";
import { getAppIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";
import { Connection } from "@/components/sync/dag";
import { toast } from "@/components/ui/use-toast";

export const SourceNode = memo(({ data, ...props }: NodeProps) => {
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

  return (
    <BaseNode
      {...props}
      data={data}
      icon={
        <img 
          src={getAppIconUrl(connection?.short_name || data.shortName)} 
          alt={connection?.name || data.name}
          className="w-8 h-8 object-contain"
        />
      }
      label={connection?.name || data.name}
      handles={{ source: true, target: false }}
      variant="square"
    />
  );
});

SourceNode.displayName = "SourceNode"; 