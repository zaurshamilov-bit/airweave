import { useEffect, useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { SyncDataSourceCard } from "./SyncDataSourceCard";
import { TooltipProvider } from "@/components/ui/tooltip";
import { apiClient } from "@/lib/api";

interface SyncDataSourceGridProps {
  onSelect: (connectionId: string, metadata: { name: string; shortName: string }) => void;
}

/**
 * Represents a Source object from the backend.
 */
interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  auth_type?: string | null;
}

/**
 * Represents a Connection object from the backend (for a source).
 */
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

interface LocalConnection extends Connection {
  isSelected?: boolean;
}

/**
 * Get connections for a specific source by matching source_id
 */
const getConnectionsForSource = (shortName: string, connections: Connection[]): Connection[] => {
  console.log("Getting connections for source:", shortName);
  console.log("Available connections:", connections);
  return connections.filter(conn => conn.short_name === shortName);
};

export const SyncDataSourceGrid = ({ onSelect }: SyncDataSourceGridProps) => {
  const [search, setSearch] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [connections, setConnections] = useState<LocalConnection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { toast } = useToast();

  /**
   * Fetch sources from the backend.
   */
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
        variant: "destructive",
        title: "Fetch sources failed",
        description: err.message || String(err),
      });
    }
  };

  /**
   * Fetch source connections from the backend.
   * This endpoint would ideally return all "source" type connections
   * so we can identify which sources are already connected.
   */
  const fetchConnections = async () => {
    try {
      const resp = await apiClient.get("/connections/list/source");
      if (!resp.ok) {
        // It's possible the user doesn't have any connections yet,
        // so handle a 404 or an empty array gracefully if needed
        if (resp.status === 404) {
          setConnections([]);
          return;
        }
        throw new Error("Failed to fetch source connections");
      }
      const data = await resp.json();
      console.log("Fetched connections:", data); // Debug log
      setConnections(data);
    } catch (err: any) {
      console.error("Error fetching connections:", err); // Debug log
      toast({
        variant: "destructive",
        title: "Fetch connections failed",
        description: err.message || String(err),
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

  /**
   * Generate a quick map to see if a short_name is connected
   * to any SourceConnection.
   */
  const shortNameIsConnected = (shortName: string) => {
    // For each connection, we want to see if the associated source
    // has that short_name and is active
    // However, we only have an ID (source_id) in the connections.
    // So we'd need to match connection.source_id to the Source's ID.
    const matchedConnection = connections.find((conn) => {
      return conn.short_name === shortName && conn.status === "active";
    });
    return Boolean(matchedConnection);
  };

  /**
   * handleSelect is triggered when the user clicks "Choose Source" or "Connect."
   * If needed, you could determine whether to skip credentials (e.g. if the
   * source is already connected). For now, we'll keep it the same as before.
   */
  const handleSelect = async (connectionId: string, metadata: { name: string; shortName: string }) => {
    onSelect(connectionId, metadata);
  };

  // Filter and sort sources similarly to the original approach
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

  return (
    <div className="space-y-6">
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <Input
          ref={searchInputRef}
          placeholder="Search apps..."
          value={search}
          disabled={isLoading}
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
      <TooltipProvider>
        {!filteredSources.length && !isLoading && (
          <div className="text-sm text-muted-foreground">
            No sources found.
          </div>
        )}
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredSources.map((source) => {
            // Find the source's connections
            const sourceConnections = getConnectionsForSource(
              source.short_name,
              connections
            );
            
            return (
              <SyncDataSourceCard
                key={source.short_name}
                shortName={source.short_name}
                name={source.name}
                description={source.description || ""}
                status={shortNameIsConnected(source.short_name) ? "connected" : "disconnected"}
                onSelect={(connectionId) => handleSelect(connectionId, { name: source.name, shortName: source.short_name })}
                connections={sourceConnections}
                authType={source.auth_type}
              />
            );
          })}
        </div>
      </TooltipProvider>
    </div>
  );
};