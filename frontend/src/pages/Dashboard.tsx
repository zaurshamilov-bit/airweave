import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Copy, Eye, Key, Plus, ExternalLink, FileText, Github } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { CollectionCard, SourceButton, ApiKeyCard, ExampleProjectCard } from "@/components/dashboard";
import { CreateCollectionDialog } from "@/components/collections/CreateCollectionDialog";
import { UnifiedDataSourceGrid } from "@/components/data-sources/UnifiedDataSourceGrid";

// Collection type definition
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Source type definition
interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  labels?: string[];
}

// Source Connection definition
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

// API Key type
interface APIKey {
  decrypted_key: string;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [apiKey, setApiKey] = useState<APIKey | null>(null);
  const [isLoadingCollections, setIsLoadingCollections] = useState(true);
  const [isLoadingSources, setIsLoadingSources] = useState(true);
  const [isLoadingApiKey, setIsLoadingApiKey] = useState(true);
  const [collectionsWithSources, setCollectionsWithSources] = useState<Record<string, SourceConnection[]>>({});
  const [showCreateCollectionDialog, setShowCreateCollectionDialog] = useState(false);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  // Fetch collections
  useEffect(() => {
    const fetchCollections = async () => {
      setIsLoadingCollections(true);
      try {
        const response = await apiClient.get("/collections");
        if (response.ok) {
          const data = await response.json();
          setCollections(data);

          // Only fetch source connections for the top 3 collections
          const topCollections = data.slice(0, 3);
          const sourcesMap: Record<string, SourceConnection[]> = {};
          for (const collection of topCollections) {
            await fetchSourceConnectionsForCollection(collection.readable_id, sourcesMap);
          }
          setCollectionsWithSources(sourcesMap);
        } else {
          console.error("Failed to load collections:", await response.text());
        }
      } catch (err) {
        console.error("Error fetching collections:", err);
      } finally {
        setIsLoadingCollections(false);
      }
    };

    fetchCollections();
  }, []);

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

  // Fetch sources
  useEffect(() => {
    const fetchSources = async () => {
      setIsLoadingSources(true);
      try {
        const response = await apiClient.get("/sources/list");
        if (response.ok) {
          const data = await response.json();
          setSources(data);
        } else {
          console.error("Failed to load sources:", await response.text());
        }
      } catch (err) {
        console.error("Error fetching sources:", err);
      } finally {
        setIsLoadingSources(false);
      }
    };

    fetchSources();
  }, []);

  // Fetch API key
  useEffect(() => {
    const fetchApiKey = async () => {
      setIsLoadingApiKey(true);
      try {
        const response = await apiClient.get("/api-keys");
        if (response.ok) {
          const data = await response.json();
          // Get the first API key if available
          if (Array.isArray(data) && data.length > 0) {
            setApiKey(data[0]);
          }
        } else {
          console.error("Failed to load API key:", await response.text());
        }
      } catch (err) {
        console.error("Error fetching API key:", err);
      } finally {
        setIsLoadingApiKey(false);
      }
    };

    fetchApiKey();
  }, []);

  const handleCreateCollection = () => {
    navigate("/collections/create");
  };

  const handleRequestNewKey = () => {
    // Placeholder for requesting a new API key
    toast.info("New API key feature coming soon");
  };

  const handleSourceClick = (sourceId: string) => {
    // Find the source with more detailed information
    const source = sources.find(s => s.id === sourceId);
    if (source) {
      // Include description if available
      const enhancedSource = {
        ...source,
        description: source.description || `Connect to your ${source.name} account`
      };
      setSelectedSource(enhancedSource);
      setShowCreateCollectionDialog(true);
    } else {
      toast.error("Source not found");
    }
  };

  // Handle collection creation
  const handleCollectionCreated = (collectionId: string, collection: any) => {
    // Now that we have the collection, we need to start the source integration flow
    // Trigger the source connection dialog/flow
    startSourceIntegration(collectionId, selectedSource!);
  };

  // Start the source integration process
  const startSourceIntegration = (collectionId: string, source: Source) => {
    // Create a custom event to trigger the source connection dialog/flow
    const event = new CustomEvent('initiate-connection', {
      detail: {
        source,
        collectionId
      }
    });
    document.dispatchEvent(event);

    // Navigate to the collection detail page where the user can see it being set up
    navigate(`/collections/${collectionId}`);
  };

  // Top 3 collections
  const topCollections = collections.slice(0, 3);

  // Example projects data
  const exampleProjects = [
    {
      id: 1,
      title: "Integrate Google Drive",
      description: "This is an example project",
    },
    {
      id: 2,
      title: "Informed Langraph Agent",
      description: "This is an example project",
    },
    {
      id: 3,
      title: "White label react app",
      description: "This is an example project",
    },
    {
      id: 4,
      title: "Custom SQL Integration",
      description: "This is an example project",
    },
    {
      id: 5,
      title: "Notion Knowledge Base",
      description: "This is an example project",
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1800px] px-4 sm:px-6 py-6 pb-8">
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
        {/* Main content (left column) */}
        <div className="md:col-span-2 lg:col-span-3 space-y-8 sm:space-y-10">
          {/* Collections Section */}
          <section>
            <div className="flex items-center justify-between mb-4 sm:mb-6">
              <h2 className="text-2xl sm:text-3xl font-bold">Collections</h2>
              <button
                onClick={() => navigate("/collections")}
                className="text-sm text-blue-600 hover:underline"
              >
                See more
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
              {isLoadingCollections ? (
                <div className="col-span-full text-center py-10 text-muted-foreground">Loading collections...</div>
              ) : topCollections.length === 0 ? (
                <div className="col-span-full text-center py-10 text-muted-foreground">No collections found</div>
              ) : (
                topCollections.map((collection) => (
                  <CollectionCard
                    key={collection.id}
                    id={collection.id}
                    name={collection.name}
                    readableId={collection.readable_id}
                    sourceConnections={collectionsWithSources[collection.readable_id] || []}
                    onClick={() => navigate(`/collections/${collection.readable_id}`)}
                  />
                ))
              )}
            </div>
          </section>

          {/* Create Collection Section */}
          <section>
            <h2 className="text-xl sm:text-2xl font-semibold mb-1 sm:mb-2">Create collection</h2>
            <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-5">
              Start with a source to add to the new collection
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
              {isLoadingSources ? (
                <div className="col-span-full h-40 flex items-center justify-center">
                  <div className="animate-pulse flex flex-col items-center">
                    <div className="h-10 w-10 bg-gray-200 dark:bg-gray-700 rounded-md mb-4"></div>
                    <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2"></div>
                    <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : sources.length === 0 ? (
                <div className="col-span-full text-center py-10 text-muted-foreground">
                  No sources found
                </div>
              ) : (
                sources.map((source) => (
                  <SourceButton
                    key={source.id}
                    id={source.id}
                    name={source.name}
                    shortName={source.short_name}
                    onClick={() => handleSourceClick(source.id)}
                  />
                ))
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="space-y-6 sm:space-y-8">
          {/* API Key Card */}
          <ApiKeyCard
            apiKey={apiKey}
            onRequestNewKey={handleRequestNewKey}
          />

          {/* Example Projects */}
          <section>
            <h2 className="text-xl sm:text-2xl font-semibold mb-1 sm:mb-2">Example projects</h2>
            <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-5">Use a template to get started</p>

            <div className="space-y-3 sm:space-y-4">
              {exampleProjects.map((project) => (
                <ExampleProjectCard
                  key={project.id}
                  id={project.id}
                  title={project.title}
                  description={project.description}
                  onClick={() => toast.info(`Opening ${project.title} template`)}
                />
              ))}
            </div>
          </section>
        </div>
      </div>

      {/* Create Collection Dialog */}
      <CreateCollectionDialog
        open={showCreateCollectionDialog}
        onOpenChange={setShowCreateCollectionDialog}
        source={selectedSource}
        onCollectionCreated={handleCollectionCreated}
      />
    </div>
  );
};

export default Dashboard;
