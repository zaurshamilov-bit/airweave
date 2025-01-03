import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { dataSources } from "@/config/dataSources";
import { useToast } from "@/components/ui/use-toast";
import { SyncDataSourceCard } from "./SyncDataSourceCard";
import { TooltipProvider } from "@/components/ui/tooltip";

interface SyncDataSourceGridProps {
  onSelect: (sourceId: string) => void;
}

export const SyncDataSourceGrid = ({ onSelect }: SyncDataSourceGridProps) => {
  const [search, setSearch] = useState("");
  const [connectedSources, setConnectedSources] = useState<string[]>(["notion", "slack"]); // Mock initial connections
  const { toast } = useToast();

  // Mock connections data with current selection
  const mockConnections = {
    notion: [
      { id: "sdfjnf2340823", name: "Main Notion", isSelected: true },
      { id: "sdjnsdfkj2349", name: "Team Notion", isSelected: false },
      { id: "not9384234", name: "Personal Notion", isSelected: false },
      { id: "not7629374", name: "Project Notion", isSelected: false }
    ],
    slack: [
      { id: "slk238923", name: "Workspace 1", isSelected: true },
      { id: "slk238924", name: "Dev Team", isSelected: false },
      { id: "slk238925", name: "Marketing", isSelected: false }
    ]
  };

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

  const handleSelect = async (sourceId: string) => {
    if (!connectedSources.includes(sourceId)) {
      setConnectedSources([...connectedSources, sourceId]);
    }
    onSelect(sourceId);
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
      <TooltipProvider>
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredSources.map((source) => (
            <SyncDataSourceCard
              key={source.short_name}
              shortName={source.short_name}
              name={source.name}
              description={source.description}
              status={connectedSources.includes(source.short_name) ? "connected" : "disconnected"}
              onSelect={() => handleSelect(source.short_name)}
              connections={mockConnections[source.short_name as keyof typeof mockConnections] || []}
            />
          ))}
        </div>
      </TooltipProvider>
    </div>
  );
};