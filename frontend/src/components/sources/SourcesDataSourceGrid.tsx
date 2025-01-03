import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { dataSources } from "@/config/dataSources";
import { useToast } from "@/components/ui/use-toast";
import { SourcesDataSourceCard } from "./SourcesDataSourceCard";
import { Connection } from "@/types";

export const SourcesDataSourceGrid = () => {
  const [search, setSearch] = useState("");
  const [connectedSources, setConnectedSources] = useState<string[]>(["notion", "slack"]);
  const { toast } = useToast();

  const mockConnections: Connection[] = [
    {
      id: "conn_1234567890",
      name: "Marketing Team Notion",
      status: "active",
      lastSync: "2 hours ago",
      syncCount: 5,
      documentsCount: 1234,
      healthScore: 95,
      createdAt: "2024-01-15",
    },
    {
      id: "conn_0987654321",
      name: "Engineering Wiki",
      status: "error",
      lastSync: "1 day ago",
      syncCount: 3,
      documentsCount: 567,
      healthScore: 45,
      createdAt: "2024-02-01",
    },
    {
      id: "conn_5432167890",
      name: "Design System Docs",
      status: "inactive",
      lastSync: "5 days ago",
      syncCount: 1,
      documentsCount: 89,
      healthScore: 75,
      createdAt: "2024-01-20",
    },
  ];

  const filteredSources = dataSources
    .filter((source) =>
      source.name.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const aConnected = connectedSources.includes(a.short_name);
      const bConnected = connectedSources.includes(b.short_name);
      if (aConnected && !bConnected) return -1;
      if (!aConnected && bConnected) return 1;
      return 0;
    });

  const handleConnect = async (sourceId: string) => {
    setConnectedSources([...connectedSources, sourceId]);
    toast({
      title: "Source Connected",
      description: `Successfully connected to ${sourceId}`,
    });
  };

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
            description={source.description}
            status={connectedSources.includes(source.short_name) ? "connected" : "disconnected"}
            onConnect={() => handleConnect(source.short_name)}
            existingConnections={connectedSources.includes(source.short_name) ? mockConnections : []}
          />
        ))}
      </div>
    </div>
  );
}