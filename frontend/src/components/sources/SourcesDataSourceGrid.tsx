import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { SourcesDataSourceCard } from "./SourcesDataSourceCard";
import { apiClient } from "@/lib/api";

interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  auth_type?: string | null;
}

interface Connection {
  id: string;
  short_name: string;
  name: string;
  organization_id: string;
  created_by_email: string;
  modified_by_email: string;
  status: "active" | "inactive" | "error";
  integration_type: string;
  integration_credential_id: string;
  source_id: string;
  modified_at: string;
}

const getConnectionsForSource = (shortName: string, connections: Connection[]): Connection[] => {
  return connections.filter(conn => conn.short_name === shortName);
};

export const SourcesDataSourceGrid = () => {
  const [search, setSearch] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  const fetchSources = async () => {
    try {
      const resp = await apiClient.get("/sources/list");
      if (!resp.ok) {
        throw new Error("Failed to fetch sources");
      }
      const data = await resp.json();
      setSources(data);
    } catch (err: any) {
      toast({
        title: "Error",
        description: "Failed to load sources",
        variant: "destructive",
      });
    }
  };

  const fetchConnections = async () => {
    try {
      const resp = await apiClient.get("/connections/list/source");
      if (!resp.ok && resp.status !== 404) {
        throw new Error("Failed to fetch source connections");
      }
      const data = await resp.json();
      setConnections(data);
    } catch (error) {
      console.error("Failed to fetch connections:", error);
      toast({
        title: "Error",
        description: "Failed to load connections",
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      await fetchSources();
      await fetchConnections();
      setIsLoading(false);
    })();
  });

  const shortNameIsConnected = (shortName: string) => {
    return connections.some(conn => 
      conn.short_name === shortName && conn.status === "active"
    );
  };

  const handleConnect = async (sourceId: string) => {
    try {
      await apiClient.post(`/connections/${sourceId}`);
      await fetchConnections(); // Refresh connections after connecting
      toast({
        title: "Source Connected",
        description: `Successfully connected to ${sourceId}`,
      });
    } catch (error) {
      console.error("Failed to connect source:", error);
      toast({
        title: "Error",
        description: "Failed to connect source",
        variant: "destructive",
      });
    }
  };

  const filteredSources = sources
    .filter((source) =>
      source.name.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const aConnected = shortNameIsConnected(a.short_name);
      const bConnected = shortNameIsConnected(b.short_name);
      if (aConnected && !bConnected) return -1;
      if (!aConnected && bConnected) return 1;
      return 0;
    });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search apps..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filteredSources.map((source) => (
          <SourcesDataSourceCard
            key={source.short_name}
            shortName={source.short_name}
            name={source.name}
            description={source.description || ""}
            status={shortNameIsConnected(source.short_name) ? "connected" : "disconnected"}
            onConnect={() => handleConnect(source.short_name)}
            connections={getConnectionsForSource(source.short_name, connections)}
          />
        ))}
      </div>
    </div>
  );
};