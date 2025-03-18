import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ChevronRight,
  Settings,
  Link as LinkIcon,
  Settings2,
  Trash2,
  Database,
  Waypoints,
  MoveUpRight,
  Search,
  MessagesSquare,
  Info,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { ModelSettings, Chat } from "./types";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl, getDestinationIconUrl } from "@/lib/utils/icons";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChatInfoSidebarProps } from "./types";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const AVAILABLE_MODELS = [
  { id: "gpt-4o", name: "GPT-4o" },
  { id: "gpt-4o-mini", name: "GPT-4o Mini" },
  { id: "o1-preview", name: "O1 Preview" },
];

// Add this custom badge style variant
const badgeVariants = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  inactive: "bg-gray-50 text-gray-600 border-gray-200",
};

export function ChatInfoSidebar({ chatInfo, onUpdateSettings }: ChatInfoSidebarProps) {
  const [modelSettings, setModelSettings] = useState<ModelSettings>(() => {
    // Try to get search_type from localStorage if it exists
    const savedSearchType = localStorage.getItem(`chat_search_type_${chatInfo.id}`);

    if (savedSearchType && ["vector", "graph", "hybrid"].includes(savedSearchType)) {
      return {
        ...chatInfo.model_settings,
        search_type: savedSearchType as "vector" | "graph" | "hybrid"
      };
    }

    return chatInfo.model_settings;
  });
  const [modelName, setModelName] = useState<string>(chatInfo.model_name);
  const [systemPrompt, setSystemPrompt] = useState<string>(
    chatInfo.system_prompt || "You are a helpful assistant that assists the user in finding information across their data sources."
  );
  const { toast } = useToast();
  const [saveTimeout, setSaveTimeout] = useState<NodeJS.Timeout | null>(null);
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const { resolvedTheme } = useTheme();

  // Track if we're currently updating search type to prevent feedback loops
  const [isUpdatingSearchType, setIsUpdatingSearchType] = useState(false);

  useEffect(() => {
    // Only update if we're not currently in the middle of a search type update
    if (!isUpdatingSearchType) {
      // Preserve search type from local state if it differs from server
      const currentSearchType = modelSettings.search_type;

      setModelSettings(prev => ({
        ...chatInfo.model_settings,
        // Preserve our locally selected search type if it exists
        search_type: currentSearchType || chatInfo.model_settings.search_type || "vector"
      }));

      setModelName(chatInfo.model_name);
    }
  }, [chatInfo.model_settings, chatInfo.model_name, isUpdatingSearchType]);

  // New useEffect to update system prompt when chatInfo changes
  useEffect(() => {
    if (chatInfo.system_prompt) {
      setSystemPrompt(chatInfo.system_prompt);
    }
  }, [chatInfo.system_prompt]);

  const handleModelChange = async (newModelName: string) => {
    setModelName(newModelName);
    try {
      // Update model_name at root level
      await onUpdateSettings({ model_name: newModelName } as any);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update model",
        variant: "destructive",
      });
    }
  };

  const handleSettingChange = (key: keyof ModelSettings, value: number | string) => {
    // Create new settings object with the updated value
    const newSettings = { ...modelSettings, [key]: value };
    setModelSettings(newSettings);

    // Clear existing timeout
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }

    // For search_type changes, apply immediately without debounce
    if (key === "search_type") {
      (async () => {
        try {
          // Update model_settings separately
          console.log(`Updating search type to: ${value}`);
          await onUpdateSettings({ model_settings: newSettings } as any);
        } catch (error) {
          // If update fails, revert the local state
          setModelSettings(modelSettings);
          toast({
            title: "Error",
            description: "Failed to update search type",
            variant: "destructive",
          });
        }
      })();
      return;
    }

    // For other settings, use debounce
    const timeout = setTimeout(async () => {
      try {
        // Update model_settings separately
        await onUpdateSettings({ model_settings: newSettings } as any);
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to save settings",
          variant: "destructive",
        });
      }
    }, 500);

    setSaveTimeout(timeout);
  };

  const handleDelete = async () => {
    try {
      await apiClient.delete(`/chat/${chatInfo.id}`);
      toast({
        title: "Chat deleted",
        description: "The chat has been deleted successfully.",
      });
      navigate('/chat');
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete chat",
        variant: "destructive",
      });
    }
  };

  // Special handler for search type changes
  const handleSearchTypeChange = async (searchType: "vector" | "graph" | "hybrid") => {
    try {
      console.log(`Changing search type to: ${searchType}`);

      // Set flag to prevent feedback loops
      setIsUpdatingSearchType(true);

      // Update UI immediately
      setModelSettings(prev => ({
        ...prev,
        search_type: searchType
      }));

      // Store in localStorage as backup
      localStorage.setItem(`chat_search_type_${chatInfo.id}`, searchType);

      // Create updated settings object
      const newSettings = {
        ...modelSettings,
        search_type: searchType
      };

      // Send update to server but don't wait for response to update UI
      const updatePromise = onUpdateSettings({ model_settings: newSettings } as any);

      // Wait for the update to complete
      await updatePromise;

      console.log(`Successfully updated search type to: ${searchType}`);
    } catch (error) {
      console.error('Error updating search type:', error);

      // Show error but KEEP the UI selection as user chose
      toast({
        title: "Warning",
        description: "Search type saved locally but server update failed.",
        variant: "destructive",
      });
    } finally {
      // Clear the update flag after a short delay to ensure state has settled
      setTimeout(() => {
        setIsUpdatingSearchType(false);
      }, 500);
    }
  };

  // Add system prompt handler
  const handleSystemPromptChange = (value: string) => {
    setSystemPrompt(value);

    // Clear existing timeout
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }

    // Set a new timeout to save the system prompt
    const timeout = setTimeout(async () => {
      try {
        await onUpdateSettings({ system_prompt: value } as any);
        toast({
          title: "System prompt saved",
          description: "Your changes have been saved.",
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to save system prompt",
          variant: "destructive",
        });
      }
    }, 1000);

    setSaveTimeout(timeout);
  };

  return (
    <>
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Chat</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this chat? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setShowDeleteDialog(false);
                void handleDelete();
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="w-[350px] border-l bg-background">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold">Chat Settings</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowDeleteDialog(true)}
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            <Settings2 className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>

        <ScrollArea className="h-[calc(100vh-65px)]">
          <div className="p-4 space-y-6">

            {/* System Prompt Section */}
            <div className="space-y-2">
              <div className="flex items-center gap-1">
                <h3 className="text-sm font-medium text-muted-foreground">SYSTEM PROMPT</h3>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex items-center justify-center"
                        aria-label="System prompt information"
                      >
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      <p>Customize instructions for the AI to better assist searching your data.</p>
                      <p>You can add context about where your information is stored or how it's organized.</p>
                      <p>Read more about it in the <a href="https://docs.google.com/document/d/1-_90000000000000000000000000000000000000000/edit?tab=t.0" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-600">docs</a>.</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <div className="rounded-lg border p-2">
                <Textarea
                  value={systemPrompt}
                  onChange={(e) => handleSystemPromptChange(e.target.value)}
                  placeholder="Enter system instructions for the AI..."
                  className="min-h-[120px] text-sm border-none focus-visible:ring-0 p-0"
                />
              </div>
            </div>

              {/* Search Settings */}
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">SEARCH SETTINGS</h3>

                  <div className="space-y-4">
                    {/* Custom search type selector using radio buttons to avoid resets */}
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Search Type</Label>

                      <div className="space-y-2 mt-2">
                        <div
                          className={`border p-2 rounded-md cursor-pointer hover:bg-primary/50 hover:text-accent-foreground transition-colors duration-200 ${modelSettings.search_type === 'hybrid' ? 'bg-primary/50 text-primary-foreground' : ''}`}
                          onClick={() => handleSearchTypeChange('hybrid')}
                        >
                          <div className="flex items-center gap-2">
                            <div className="flex items-center">
                              <Waypoints className="h-4 w-4" />
                              <span className="ml-1 text-xs font-bold">+</span>
                              <MoveUpRight className="h-4 w-4" />
                            </div>
                            <div className="font-medium">Agentic Hybrid Search</div>
                          </div>
                          <div className="text-xs">Combine vector and graph search for comprehensive results</div>
                        </div>
                        <div
                          className={`border p-2 rounded-md cursor-pointer hover:bg-primary/50 hover:text-accent-foreground transition-colors duration-200 ${modelSettings.search_type === 'vector' ? 'bg-primary/50 text-primary-foreground' : ''}`}
                          onClick={() => handleSearchTypeChange('vector')}
                        >
                          <div className="flex items-center gap-2">
                            <MoveUpRight className="h-4 w-4" />
                            <div className="font-medium">Vector Search</div>
                          </div>
                          <div className="text-xs">Search using embeddings for semantic similarity</div>
                        </div>

                        <div
                          className={`border p-2 rounded-md cursor-pointer hover:bg-primary/50 hover:text-accent-foreground transition-colors duration-200 ${modelSettings.search_type === 'graph' ? 'bg-primary/50 text-primary-foreground' : ''}`}
                          onClick={() => handleSearchTypeChange('graph')}
                        >
                          <div className="flex items-center gap-2">
                            <Waypoints className="h-4 w-4" />
                            <div className="font-medium">Graph Search</div>
                          </div>
                          <div className="text-xs">Search using graph relationships between entities</div>
                        </div>
                      </div>
                    </div>

                    {/* Show info for graph search if selected but not available */}
                    {modelSettings.search_type === "graph" && (
                      <div className="rounded-md p-2 text-xs text-muted-foreground bg-background/50">
                        <p>
                          <strong>Note:</strong> Graph search requires a properly configured Neo4j instance.
                          If unavailable, results may fall back to vector search.
                        </p>
                      </div>
                    )}

                    {/* Show info for hybrid search if selected */}
                    {modelSettings.search_type === "hybrid" && (
                      <div className=" rounded-md p-2 text-xs text-muted-foreground bg-background/50">
                        <p>
                          <strong>Note:</strong> Hybrid search combines results from both vector and graph search.
                          Both Weaviate and Neo4j must be configured for optimal results.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            {/* Chat Details Section */}
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-muted-foreground">CHAT DETAILS</h3>
                <div className="rounded-lg border p-3 space-y-3">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Name</Label>
                    <p className="text-sm font-medium">{chatInfo.name}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Chat ID</Label>
                    <p className="text-xs font-mono text-muted-foreground">{chatInfo.id}</p>
                  </div>
                  {chatInfo.description && (
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Description</Label>
                      <p className="text-sm">{chatInfo.description}</p>
                    </div>
                  )}
                </div>
              </div>


              {/* Data Connection Section */}
              {chatInfo.sync && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-muted-foreground">DATA CONNECTION</h3>
                  <div className="rounded-lg border p-3 space-y-4">
                    {/* Sync Details */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{chatInfo.sync.name}</span>
                        <Badge
                          className={cn(
                            "text-[10px] font-medium px-2 py-0.5 border",
                            chatInfo.sync.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                          )}
                        >
                          {chatInfo.sync.status}
                        </Badge>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Sync ID</Label>
                        <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.id}</p>
                      </div>
                    </div>

                    <Separator />

                    {/* Source Connection */}
                    {chatInfo.sync.source_connection && (
                      <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">Source</Label>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <img
                                src={getAppIconUrl(chatInfo.sync.source_connection.short_name, resolvedTheme)}
                                alt={chatInfo.sync.source_connection.source?.name}
                                className="h-5 w-5"
                              />
                              <span className="text-sm">{chatInfo.sync.source_connection.source?.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {chatInfo.sync.source_connection.source?.app_url && (
                                <a
                                  href={chatInfo.sync.source_connection.source.app_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-muted-foreground hover:text-primary"
                                >
                                  <LinkIcon className="h-3 w-3" />
                                </a>
                              )}
                              <Badge
                                className={cn(
                                  "text-[10px] font-medium px-2 py-0.5 border",
                                  chatInfo.sync.source_connection.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                                )}
                              >
                                {chatInfo.sync.source_connection.status}
                              </Badge>
                            </div>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Connection ID</Label>
                            <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.source_connection.id}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    <Separator />

                    {/* Destination */}
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Destination</Label>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <img
                            src={getDestinationIconUrl(
                              chatInfo.sync.destination_connection?.short_name || "weaviate_native"
                            )}
                            alt={chatInfo.sync.destination_connection?.destination?.name || "Native Weaviate"}
                            className="h-5 w-5"
                          />
                          <span className="text-sm">
                            {chatInfo.sync.destination_connection?.destination?.name || "Native Weaviate"}
                          </span>
                        </div>
                        {chatInfo.sync.destination_connection && (
                          <>
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground">Connection ID</Label>
                              <p className="text-xs font-mono text-muted-foreground">{chatInfo.sync.destination_connection.id}</p>
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs text-muted-foreground">Status</Label>
                              <Badge
                                className={cn(
                                  "text-[10px] font-medium px-2 py-0.5 border",
                                  chatInfo.sync.destination_connection.status === 'active' ? badgeVariants.active : badgeVariants.inactive
                                )}
                              >
                                {chatInfo.sync.destination_connection.status}
                              </Badge>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Model Settings Section */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-muted-foreground">MODEL SETTINGS</h3>
                <div className="rounded-lg border p-3 space-y-4">
                  {/* Model Selection */}
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Model</Label>
                    <Select
                      value={modelName}
                      onValueChange={handleModelChange}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {AVAILABLE_MODELS.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Temperature */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Temperature</Label>
                      <span className="text-xs">{modelSettings.temperature?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.temperature ?? 0.7]}
                      min={0}
                      max={1}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("temperature", value)}
                    />
                  </div>

                  {/* Max Tokens */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Max Tokens</Label>
                      <span className="text-xs">{modelSettings.max_tokens}</span>
                    </div>
                    <Slider
                      value={[modelSettings.max_tokens ?? 1000]}
                      min={100}
                      max={4000}
                      step={100}
                      onValueChange={([value]) => handleSettingChange("max_tokens", value)}
                    />
                  </div>

                  {/* Top P */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Top P</Label>
                      <span className="text-xs">{modelSettings.top_p?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.top_p ?? 1]}
                      min={0}
                      max={1}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("top_p", value)}
                    />
                  </div>

                  {/* Frequency Penalty */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Frequency Penalty</Label>
                      <span className="text-xs">{modelSettings.frequency_penalty?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.frequency_penalty ?? 0]}
                      min={0}
                      max={2}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("frequency_penalty", value)}
                    />
                  </div>

                  {/* Presence Penalty */}
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label className="text-xs text-muted-foreground">Presence Penalty</Label>
                      <span className="text-xs">{modelSettings.presence_penalty?.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[modelSettings.presence_penalty ?? 0]}
                      min={0}
                      max={2}
                      step={0.1}
                      onValueChange={([value]) => handleSettingChange("presence_penalty", value)}
                    />
                  </div>
                </div>
              </div>

            </div>
          </div>
        </ScrollArea>
      </div>
    </>
  );
}
