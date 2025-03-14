import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { useState, useEffect } from "react";
import { Connection } from "@/types";
import { getAppIconUrl } from "@/lib/utils/icons";
import { ConnectionsList } from "./ConnectionsList";
import { useTheme } from "@/lib/theme-provider";
import { Box, Plug, Database, Info, LayoutDashboard, Settings2, Tag, Code, Github, Play, Unplug, Search, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LabelBadge } from "../data-sources/LabelBadge";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { format } from "date-fns";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

interface ConnectionCardProps {
  connection: Connection;
  onSync?: () => void;
  onDisconnect?: () => void;
  onViewDetails?: () => void;
}

function ConnectionCard({ connection, onSync, onDisconnect, onViewDetails }: ConnectionCardProps) {
  const getStatusBadge = (status: string) => {
    const statusUpper = status.toUpperCase();
    let variant: "default" | "secondary" | "destructive" = "secondary";

    if (statusUpper === "ACTIVE") variant = "default";
    if (statusUpper === "ERROR") variant = "destructive";

    return (
      <Badge variant={variant} className="text-xs">
        {status}
      </Badge>
    );
  };

  const formattedDate = (dateString: string | undefined) => {
    if (!dateString) return "Not available";

    try {
      return format(new Date(dateString), "MMM d, yyyy");
    } catch (e) {
      return "Invalid date";
    }
  };

  return (
    <div className="bg-card border border-border/70 rounded-lg overflow-hidden">
      <div className="p-4 pb-3 flex justify-between items-start">
        <div>
          <h3 className="font-medium flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            {connection.name}
          </h3>
          <code className="text-xs px-1.5 py-0.5 rounded-sm bg-muted font-mono mt-1 inline-block">
            {connection.id}
          </code>
        </div>
        {getStatusBadge(connection.status)}
      </div>

      <div className="px-4 py-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm border-t border-border/10">
        <div>
          <div className="text-muted-foreground text-xs">Created by:</div>
          <div className="font-medium truncate">{connection.created_by_email || "Unknown"}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Modified by:</div>
          <div className="font-medium truncate">{connection.modified_by_email || "Unknown"}</div>
        </div>
        <div className="mt-1">
          <div className="text-muted-foreground text-xs">Created at:</div>
          <div className="font-medium">{formattedDate(connection.createdAt)}</div>
        </div>
        <div className="mt-1">
          <div className="text-muted-foreground text-xs">Last modified:</div>
          <div className="font-medium">{formattedDate(connection.modified_at)}</div>
        </div>
      </div>

      <div className="p-3 bg-muted/10 border-t border-border/70 flex justify-end gap-2">
        {onDisconnect && (
          <Button variant="destructive" size="sm" onClick={onDisconnect}>
            <Unplug className="h-4 w-4 mr-1" />
            Disconnect
          </Button>
        )}
      </div>
    </div>
  );
}

interface ManageSourceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  shortName: string;
  description: string;
  onConnect: () => void;
  existingConnections?: Connection[];
  isLoading?: boolean;
  labels?: string[];
  entityCount?: number;
  authType?: string | null;
}

export function ManageSourceDialog({
  open,
  onOpenChange,
  name,
  shortName,
  description,
  onConnect,
  existingConnections = [],
  isLoading = false,
  labels = [],
  entityCount = 0,
  authType,
}: ManageSourceDialogProps) {
  const [search, setSearch] = useState("");
  const [selectedTab, setSelectedTab] = useState("information");
  const { resolvedTheme } = useTheme();
  const [isDisconnectDialogOpen, setIsDisconnectDialogOpen] = useState(false);
  const [connectionToDisconnect, setConnectionToDisconnect] = useState<Connection | null>(null);

  const filteredConnections = existingConnections.filter(conn =>
    conn.name.toLowerCase().includes(search.toLowerCase())
  );

  // Reset tab to information when dialog opens
  useEffect(() => {
    if (open) {
      setSelectedTab("information");
    }
  }, [open]);

  const handleDisconnect = async () => {
    if (!connectionToDisconnect) return;

    try {
      await apiClient.put(`/connections/disconnect/source/${connectionToDisconnect.id}`);
      toast.success(`Disconnected ${connectionToDisconnect.name} successfully`);
      // You would typically refresh the connections list here
      setConnectionToDisconnect(null);
      setIsDisconnectDialogOpen(false);
    } catch (error) {
      toast.error("Failed to disconnect connection");
    }
  };

  const handleSyncConnection = async (connectionId: string) => {
    try {
      await apiClient.post(`/sync/run/${connectionId}`);
      toast.success("Sync started successfully");
    } catch (error) {
      toast.error("Failed to start sync");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[1400px] max-h-[95vh] overflow-hidden p-0">
        <div className="flex h-[900px]">
          {/* Sidebar Navigation */}
          <div className="w-[220px] border-r border-border/70 bg-muted/30 p-4 flex flex-col">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 flex items-center justify-center">
                <img
                  src={getAppIconUrl(shortName, resolvedTheme)}
                  alt={`${name} icon`}
                  className="w-10 h-10"
                />
              </div>
              <div className="flex flex-col">
                <h3 className="text-base font-semibold">{name}</h3>
                {authType && (
                  <span className="text-xs px-1.5 py-0.5 rounded-sm bg-gray-100 dark:bg-gray-800 font-medium text-muted-foreground mt-1 inline-block w-fit">
                    {authType.includes("oauth2") ? "OAUTH2" : authType.replace(/_/g, " ").toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-1">
              <Button
                variant={selectedTab === "information" ? "default" : "ghost"}
                className={cn("w-full justify-start",
                  selectedTab === "information" ? "bg-primary/10 text-primary hover:bg-primary/20" : ""
                )}
                onClick={() => setSelectedTab("information")}
              >
                <Info className="mr-2 h-4 w-4" />
                Information
              </Button>
              <Button
                variant={selectedTab === "connections" ? "default" : "ghost"}
                className={cn("w-full justify-start",
                  selectedTab === "connections" ? "bg-primary/10 text-primary hover:bg-primary/20" : ""
                )}
                onClick={() => setSelectedTab("connections")}
              >
                <Plug className="mr-2 h-4 w-4" />
                Connections
                {existingConnections.length > 0 && (
                  <Badge variant="outline" className="ml-auto">{existingConnections.length}</Badge>
                )}
              </Button>
              <Button
                variant={selectedTab === "entities" ? "default" : "ghost"}
                className={cn("w-full justify-start",
                  selectedTab === "entities" ? "bg-primary/10 text-primary hover:bg-primary/20" : ""
                )}
                onClick={() => setSelectedTab("entities")}
              >
                <Database className="mr-2 h-4 w-4" />
                Entities
                {entityCount > 0 && (
                  <Badge variant="outline" className="ml-auto">{entityCount}</Badge>
                )}
              </Button>
            </div>
            <div className="mt-auto text-xs text-muted-foreground">
              <p>Last updated: {new Date().toLocaleDateString()}</p>
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <DialogHeader className="px-6 py-4 border-b border-border/70">
              <div className="flex justify-between items-center">
                <div>
                  <DialogTitle>
                    {selectedTab === "information" && "Source Information"}
                    {selectedTab === "connections" && "Manage Connections"}
                    {selectedTab === "entities" && "View Entities"}
                  </DialogTitle>
                  <DialogDescription>
                    {selectedTab === "information" && "Overview and details about this data source"}
                    {selectedTab === "connections" && "Configure and manage connections to this source"}
                    {selectedTab === "entities" && "Explore entities synced from this source"}
                  </DialogDescription>
                </div>
                <Button onClick={onConnect} variant="default" size="sm" className="mr-8">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Connection
                </Button>
              </div>
            </DialogHeader>

            <ScrollArea className="flex-1">
              <div className="p-6">
                {/* Information Tab */}
                {selectedTab === "information" && (
                  <div className="space-y-8">
                    <div className="max-w-3xl">
                      <h3 className="text-lg font-semibold mb-3">Overview</h3>
                      <p className="text-sm text-muted-foreground">{description}</p>
                    </div>

                    {/* Labels Section - More prominent */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Tag className="h-5 w-5" />
                        <h3 className="text-lg font-semibold">Labels</h3>
                      </div>

                      {labels.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {labels.slice(0, 3).map((label) => (
                            <LabelBadge key={label} label={label} />
                          ))}
                          {labels.length > 3 && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-500/15 text-gray-600 dark:text-gray-400">
                                  +{labels.length - 3}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                <div className="flex flex-wrap gap-1.5 max-w-[240px]">
                                  {labels.slice(3).map((label) => (
                                    <LabelBadge key={label} label={label} />
                                  ))}
                                </div>
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      ) : (
                        <div className="text-sm text-muted-foreground">
                          No labels have been added to this source.
                        </div>
                      )}
                    </div>

                    {/* Source Code Link */}
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Github className="h-5 w-5" />
                        <h3 className="text-lg font-semibold">Source Code</h3>
                      </div>
                      <div className="text-sm">
                        <a
                          href={`https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/${shortName}.py`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline flex items-center gap-2"
                        >
                          View source implementation for {name}
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-external-link"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" x2="21" y1="14" y2="3"/></svg>
                        </a>
                      </div>
                    </div>
                  </div>
                )}

                {/* Connections Tab */}
                {selectedTab === "connections" && (
                  <div className="space-y-6">
                    <div className="relative flex-1 max-w-sm">
                      <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search connections..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9"
                      />
                    </div>

                    {filteredConnections.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredConnections.map((connection) => (
                          <ConnectionCard
                            key={connection.id}
                            connection={connection}
                            onDisconnect={() => {
                              setConnectionToDisconnect(connection);
                              setIsDisconnectDialogOpen(true);
                            }}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed rounded-lg bg-muted/20">
                        <Plug className="h-12 w-12 text-muted-foreground/50 mb-4" />
                        <h3 className="text-lg font-medium mb-2">No connections found</h3>
                        <p className="text-sm text-muted-foreground max-w-md">
                          {search ? "No connections match your search criteria." : "You haven't created any connections to this source yet."}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Entities Tab */}
                {selectedTab === "entities" && (
                  <div className="space-y-6">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-semibold">Synced Entities</h3>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Box className="w-4 h-4" />
                        <span>{entityCount > 0 ? `${entityCount} entities` : "No entities synced yet"}</span>
                      </div>
                    </div>

                    {entityCount > 0 ? (
                      <div className="rounded-lg border border-border/70 overflow-hidden">
                        <div className="bg-muted/30 p-3 grid grid-cols-4 gap-4 text-sm font-medium">
                          <div>ID</div>
                          <div>Type</div>
                          <div>Last Synced</div>
                          <div>Status</div>
                        </div>
                        <div className="divide-y divide-border/70">
                          <div className="p-3 grid grid-cols-4 gap-4 text-sm items-center">
                            <div className="text-muted-foreground">entity-1234</div>
                            <div>Document</div>
                            <div>2 hours ago</div>
                            <Badge variant="outline" className="justify-self-start">Synced</Badge>
                          </div>
                          <div className="p-3 grid grid-cols-4 gap-4 text-sm items-center">
                            <div className="text-muted-foreground">entity-5678</div>
                            <div>User</div>
                            <div>5 hours ago</div>
                            <Badge variant="outline" className="justify-self-start">Synced</Badge>
                          </div>
                          <div className="p-3 grid grid-cols-4 gap-4 text-sm items-center">
                            <div className="text-muted-foreground">entity-9012</div>
                            <div>Folder</div>
                            <div>1 day ago</div>
                            <Badge variant="outline" className="justify-self-start">Synced</Badge>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed rounded-lg bg-muted/20">
                        <Database className="h-12 w-12 text-muted-foreground/50 mb-4" />
                        <h3 className="text-lg font-medium mb-2">No entities synced yet</h3>
                        <p className="text-sm text-muted-foreground max-w-md">
                          Connect to this source and run a sync to view entities extracted from this data source.
                        </p>
                      </div>
                    )}

                    {entityCount > 0 && (
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm">
                          <LayoutDashboard className="mr-2 h-4 w-4" />
                          View in Data Explorer
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>

        {/* Disconnect confirmation dialog */}
        <Dialog open={isDisconnectDialogOpen} onOpenChange={setIsDisconnectDialogOpen}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Unplug className="h-5 w-5 text-destructive" />
                Disconnect Connection
              </DialogTitle>
              <DialogDescription className="pt-2">
                Are you sure you want to disconnect <span className="font-medium">{connectionToDisconnect?.name}</span>?
                This will stop syncing data from this connection.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                onClick={() => setIsDisconnectDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDisconnect}
              >
                Disconnect
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
