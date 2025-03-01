import { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { SourcesDataSourceCard } from "./SourcesDataSourceCard";
import { apiClient } from "@/lib/api";
import { Connection } from "@/types";

interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  auth_type?: string | null;
}

const getConnectionsForSource = (shortName: string, connections: Connection[]): Connection[] => {
  return connections.filter(conn => conn.short_name === shortName);
};

export const SourcesDataSourceGrid = () => {
  const [search, setSearch] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
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
  }, []);

  // Add keyboard shortcut handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for Command+K (Mac) or Control+K (Windows/Linux)
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

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
      // First sort by connection status
      const aConnected = shortNameIsConnected(a.short_name);
      const bConnected = shortNameIsConnected(b.short_name);
      if (aConnected && !bConnected) return -1;
      if (!aConnected && bConnected) return 1;
      // Then sort alphabetically by name
      return a.name.localeCompare(b.name);
    });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <Input
          ref={searchInputRef}
          placeholder="Search apps..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setIsSearchFocused(true)}
          onBlur={() => setIsSearchFocused(false)}
          className="pl-9"
        />
        {!isSearchFocused && (
          <div className="absolute right-3 top-3 text-xs text-muted-foreground pointer-events-none">
            ⌘K
          </div>
        )}
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