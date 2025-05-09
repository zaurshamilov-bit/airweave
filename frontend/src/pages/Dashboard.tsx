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
  key_prefix: string;
  plain_key?: string;
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
  const [copySuccess, setCopySuccess] = useState(false);
  const [collectionsWithSources, setCollectionsWithSources] = useState<Record<string, SourceConnection[]>>({});

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

  const handleCopyApiKey = () => {
    if (apiKey?.plain_key) {
      navigator.clipboard.writeText(apiKey.plain_key);
      setCopySuccess(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  // Get source icon
  const getSourceIcon = (shortName: string) => {
    return (
      <div className="flex items-center justify-center w-10 h-10 overflow-hidden">
        <img
          src={getAppIconUrl(shortName, resolvedTheme)}
          alt={`${shortName} icon`}
          className="w-9 h-9 object-contain"
          onError={(e) => {
            // Fallback to initials if icon fails to load
            e.currentTarget.style.display = 'none';
            e.currentTarget.parentElement!.classList.add(getColorClass(shortName));
            e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
          }}
        />
      </div>
    );
  };

  // Get color class based on shortName
  const getColorClass = (shortName: string) => {
    const colors = [
      "bg-blue-500",
      "bg-green-500",
      "bg-purple-500",
      "bg-orange-500",
      "bg-pink-500",
      "bg-indigo-500",
      "bg-red-500",
      "bg-yellow-500",
    ];

    // Hash the short name to get a consistent color
    const index = shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
    return colors[index];
  };

  // Navigation to collection detail
  const goToCollection = (readableId: string) => {
    navigate(`/collections/${readableId}`);
  };

  // Top 3 collections
  const topCollections = collections.slice(0, 3);

  // Example projects - this is placeholder data
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
    <div className="px-6 py-6 pb-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content (left column) */}
        <div className="lg:col-span-2 space-y-10">
          {/* Collections Section */}
          <section>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-3xl font-bold">Collections</h2>
              <button
                onClick={() => navigate("/collections")}
                className="text-sm text-blue-600 hover:underline"
              >
                See more
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {isLoadingCollections ? (
                <div className="col-span-3 text-center py-10 text-muted-foreground">Loading collections...</div>
              ) : topCollections.length === 0 ? (
                <div className="col-span-3 text-center py-10 text-muted-foreground">No collections found</div>
              ) : (
                topCollections.map((collection) => (
                  <div
                    key={collection.id}
                    className="relative border border-zinc-200 rounded-lg hover:border-zinc-300 hover:shadow-sm transition-all cursor-pointer bg-white overflow-hidden"
                    onClick={() => goToCollection(collection.readable_id)}
                  >
                    <div className="p-6 pb-24">
                      {/* Collection title & URL - large handwritten style */}
                      <div>
                        <h3 className="text-2xl font-medium mb-2" style={{ fontFamily: 'var(--font-sans)' }}>
                          {collection.name}
                        </h3>
                        <p className="text-sm text-zinc-500">
                          respectable-{collection.readable_id}.airweave.ai
                        </p>
                      </div>
                    </div>

                    {/* Source connection icons - bottom right */}
                    <div className="absolute bottom-6 right-6">
                      <div className="relative" style={{ width: "5rem", height: "2.5rem" }}>
                        {collectionsWithSources[collection.readable_id]?.map((connection, index, arr) => (
                          <div
                            key={connection.id}
                            className="absolute w-12 h-12 rounded-md border border-zinc-200 p-1 flex items-center justify-center overflow-hidden bg-white shadow-sm"
                            style={{
                              right: `${index * 15}px`,
                              zIndex: arr.length - index
                            }}
                          >
                            <img
                              src={getAppIconUrl(connection.short_name, resolvedTheme)}
                              alt={connection.name}
                              className="max-w-full max-h-full w-auto h-auto object-contain"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* View & Edit button - left bottom */}
                    <div className="absolute bottom-6 left-6">
                      <Button
                        variant="outline"
                        className="h-10 w-32 rounded-md border-zinc-300 flex items-center justify-center gap-2 hover:bg-zinc-50"
                      >
                        <Eye className="h-4 w-4" /> View & edit
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* Create Collection Section */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Create collection</h2>
            <p className="text-sm text-muted-foreground mb-5">Start with a source to add to the new collection</p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {isLoadingSources ? (
                <div className="col-span-4 text-center py-10 text-muted-foreground">Loading sources...</div>
              ) : sources.length === 0 ? (
                <div className="col-span-4 text-center py-10 text-muted-foreground">No sources found</div>
              ) : (
                sources.map((source) => (
                  <div
                    key={source.id}
                    className="border border-zinc-200 rounded-lg hover:border-zinc-300 hover:shadow-sm transition-all cursor-pointer overflow-hidden group"
                  >
                    <div className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getSourceIcon(source.short_name)}
                        <span className="text-sm font-medium">{source.name}</span>
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 rounded-full bg-zinc-100 hover:bg-zinc-200 group-hover:bg-blue-100 group-hover:text-blue-600 transition-all"
                      >
                        <Plus className="h-4 w-4 group-hover:h-5 group-hover:w-5 transition-all" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="space-y-8">
          {/* API Key Card */}
          <div className="border border-zinc-200 rounded-lg overflow-hidden">
            <div className="p-5">
              <div className="flex items-center mb-1">
                <Key className="h-4 w-4 mr-1.5 text-zinc-500" />
                <h3 className="text-sm font-medium">API Key</h3>
              </div>
              <p className="text-xs text-zinc-500 mb-4">Store your API keys securely away</p>
              <div className="flex items-center">
                <Input
                  value={apiKey?.plain_key || `tc-${Array(30).fill("*").join("")}0007`}
                  className="text-xs font-mono h-9 bg-zinc-50 border-zinc-200"
                  readOnly
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-1 h-9 w-9"
                  onClick={handleCopyApiKey}
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
              <div className="mt-2 text-right">
                <button className="text-xs text-blue-600 hover:underline">
                  Need another API key?
                </button>
              </div>
            </div>
          </div>

          {/* Example Projects */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Example projects</h2>
            <p className="text-sm text-muted-foreground mb-5">Use a template to get started</p>

            <div className="space-y-4">
              {exampleProjects.map((project) => (
                <div key={project.id} className="border border-zinc-200 rounded-lg hover:border-zinc-300 hover:shadow-sm transition-all overflow-hidden group cursor-pointer">
                  <div className="p-6">
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 mt-0.5">
                        <div className="p-2 rounded-md bg-blue-50 group-hover:bg-blue-100 transition-all">
                          <Github className="h-5 w-5 text-blue-600" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-base group-hover:text-blue-600 transition-colors">{project.title}</h3>
                        <p className="text-sm text-zinc-500 mt-2">{project.description}</p>
                      </div>
                      <Button variant="ghost" size="icon" className="h-6 w-6 -mt-1 -mr-2 group-hover:bg-blue-100 group-hover:text-blue-600 transition-all">
                        <ExternalLink className="h-3.5 w-3.5 text-zinc-400 group-hover:h-4 group-hover:w-4 transition-all" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
