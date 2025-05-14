import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { CollectionCard } from "@/components/dashboard";

// Collection type definition
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Source Connection definition
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

const CollectionsView = () => {
  const navigate = useNavigate();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [filteredCollections, setFilteredCollections] = useState<Collection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [collectionsWithSources, setCollectionsWithSources] = useState<Record<string, SourceConnection[]>>({});

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);

  // Fetch source connections for a specific collection
  const fetchSourceConnectionsForCollection = async (
    collectionId: string,
    sourcesMap: Record<string, SourceConnection[]>
  ) => {
    try {
      const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);
      if (response.ok) {
        const data = await response.json();
        sourcesMap[collectionId] = data;
      } else {
        console.error(`Failed to load source connections for collection ${collectionId}:`, await response.text());
        sourcesMap[collectionId] = [];
      }
    } catch (err) {
      console.error(`Error fetching source connections for collection ${collectionId}:`, err);
      sourcesMap[collectionId] = [];
    }
  };

  // Fetch all collections
  const fetchCollections = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get("/collections");
      if (response.ok) {
        const data = await response.json();
        setCollections(data);
        setFilteredCollections(data);

        // Fetch source connections for all collections
        const sourcesMap: Record<string, SourceConnection[]> = {};
        for (const collection of data) {
          await fetchSourceConnectionsForCollection(collection.readable_id, sourcesMap);
        }
        setCollectionsWithSources(sourcesMap);
      } else {
        console.error("Failed to load collections:", await response.text());
      }
    } catch (err) {
      console.error("Error fetching collections:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch collections on component mount
  useEffect(() => {
    fetchCollections();
  }, []);

  // Filter collections based on search query
  useEffect(() => {
    if (searchQuery.trim() === "") {
      setFilteredCollections(collections);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = collections.filter(
        (collection) =>
          collection.name.toLowerCase().includes(query) ||
          collection.readable_id.toLowerCase().includes(query)
      );
      setFilteredCollections(filtered);
    }
  }, [searchQuery, collections]);

  // Refresh collections after creating a new one
  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedSourceId(null);
    fetchCollections();
  };

  // Open create collection dialog
  const handleCreateCollection = () => {
    // For simplicity, we're not selecting a specific source here
    // You could modify this to show a source selection first
    setSelectedSourceId("");
    setDialogOpen(true);
  };

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">

      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1">Collections</h1>
          <p className="text-sm text-muted-foreground">
            View and manage all your collections
          </p>
        </div>
        <Button
          onClick={handleCreateCollection}
          className="bg-primary hover:bg-primary/90 text-white rounded-lg h-9 px-4"
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Collection
        </Button>
      </div>

      {/* Search bar */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search collections by name or ID..."
            className="pl-10 h-10 rounded-xl border-border focus:border-text/50 focus:ring-0 focus:ring-offset-0 focus:ring-text/50 dark:bg-background dark:focus:bg-background/80 transition-colors"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Collections Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-6 sm:gap-8 auto-rows-fr">
        {isLoading ? (
          Array.from({ length: 8 }).map((_, index) => (
            <div
              key={index}
              className="h-[220px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
            />
          ))
        ) : filteredCollections.length === 0 ? (
          <div className="col-span-full text-center py-20 text-muted-foreground">
            {searchQuery ? "No collections found matching your search" : "No collections found"}
          </div>
        ) : (
          filteredCollections.map((collection) => (
            <CollectionCard
              key={collection.id}
              id={collection.id}
              name={collection.name}
              readableId={collection.readable_id}
              sourceConnections={collectionsWithSources[collection.readable_id] || []}
              status={collection.status}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default CollectionsView;
