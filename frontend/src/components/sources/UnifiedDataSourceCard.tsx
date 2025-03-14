import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Info, ChevronDown, Check, CircleDot } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";
import { useTheme } from "@/lib/theme-provider";
import { Connection } from "@/types";

export interface UnifiedDataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  connections: Connection[];
  authType?: string | null;

  // Mode configuration
  mode: "select" | "manage";

  // Common callbacks
  onInfoClick?: () => void;

  // Select mode properties
  onSelect?: (connectionId: string) => void;
  onAddConnection?: () => void;

  // Manage mode properties
  onManage?: () => void;

  // Custom rendering
  renderConnectionsIndicator?: () => React.ReactNode;
  renderBottomActions?: () => React.ReactNode;

  // Additional dialogs/wizards
  renderDialogs?: () => React.ReactNode;
}

export function UnifiedDataSourceCard({
  shortName,
  name,
  description,
  status,
  connections = [],
  authType,
  mode = "select",
  onInfoClick,
  onSelect,
  onAddConnection,
  onManage,
  renderConnectionsIndicator,
  renderBottomActions,
  renderDialogs,
}: UnifiedDataSourceCardProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const { resolvedTheme } = useTheme();
  const activeConnections = connections.filter(conn => conn.status === "active");

  useEffect(() => {
    if (mode === "select" && connections.length > 0) {
      const sortedConnections = [...connections].sort((a, b) =>
        new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
      );
      setSelectedConnectionId(sortedConnections[0]?.id || null);
    }
  }, [connections, mode]);

  const handlePrimaryAction = () => {
    if (mode === "select") {
      if (status === "connected" && selectedConnectionId && onSelect) {
        onSelect(selectedConnectionId);
      } else if (onAddConnection) {
        onAddConnection();
      }
    } else if (mode === "manage" && onManage) {
      onManage();
    }
  };

  const handleConnectionSelect = (connectionId: string) => {
    setSelectedConnectionId(connectionId);
    setOpen(false);
    if (onSelect) {
      onSelect(connectionId);
    }
  };

  const handleAddNewConnection = () => {
    setOpen(false);
    if (onAddConnection) {
      onAddConnection();
    }
  };

  return (
    <>
      <Card className="w-full min-h-[240px] flex flex-col justify-between overflow-hidden">
        <CardHeader className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start space-x-3 flex-1 min-w-0">
              <div className="w-8 h-8 shrink-0 flex items-center justify-center">
                <img
                  src={getAppIconUrl(shortName, resolvedTheme)}
                  alt={`${name} icon`}
                  className="w-6 h-6"
                />
              </div>
              <div className="min-w-0 flex-1">
                <CardTitle className="text-lg mb-1 line-clamp-1">{name}</CardTitle>
                <CardDescription className="line-clamp-2">{description}</CardDescription>
              </div>
            </div>

            {mode === "select" && onInfoClick && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onInfoClick}>
                    <Info className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Click to learn more about this source</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </CardHeader>

        <CardContent className="p-4 pt-0 flex-grow">
          {/* Custom connections indicator or default for manage mode */}
          {renderConnectionsIndicator ? (
            renderConnectionsIndicator()
          ) : (
            mode === "manage" && status === "connected" && (
              <div className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium",
                "bg-primary/10 text-primary"
              )}>
                <CircleDot className="w-3 h-3" />
                {activeConnections.length} active connection{activeConnections.length !== 1 ? 's' : ''}
              </div>
            )
          )}

          <p className="text-sm text-muted-foreground line-clamp-3 mt-2">
            Extract and sync your {name} data to your vector database of choice.
          </p>
        </CardContent>

        <CardFooter className="p-4 pt-0">
          {renderBottomActions ? (
            renderBottomActions()
          ) : (
            <div className="flex w-full gap-1">
              <Button
                onClick={handlePrimaryAction}
                variant={status === "connected" ? "secondary" : "default"}
                className={mode === "manage" ? "w-full" : "flex-1"}
              >
                {mode === "select"
                  ? (status === "connected" ? "Choose Source" : "Connect")
                  : "Manage Source"
                }
              </Button>

              {mode === "select" && (
                <DropdownMenu open={open} onOpenChange={setOpen}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant={status === "connected" ? "secondary" : "default"}
                      className="px-2"
                    >
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="w-[280px]"
                    style={{
                      maxHeight: '300px',
                      overflowY: 'auto'
                    }}
                  >
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={handleAddNewConnection}
                    >
                      <span className="font-medium text-primary">Add new connection</span>
                    </DropdownMenuItem>

                    {connections.length > 0 && <DropdownMenuSeparator />}

                    {[...connections]
                      .sort((a, b) => {
                        return new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime();
                      })
                      .map((connection) => (
                        <DropdownMenuItem
                          key={connection.id}
                          className="cursor-pointer"
                          onClick={() => handleConnectionSelect(connection.id)}
                        >
                          <div className="flex items-center justify-between w-full">
                            <div className="flex flex-col">
                              <span className="font-medium">{connection.name}</span>
                              <span className="text-xs text-muted-foreground">
                                ID: {connection.id}
                              </span>
                            </div>
                            {selectedConnectionId === connection.id && (
                              <Check className="h-4 w-4 text-primary ml-2" />
                            )}
                          </div>
                        </DropdownMenuItem>
                      ))
                    }
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          )}
        </CardFooter>
      </Card>

      {/* Render any dialogs/modals if provided */}
      {renderDialogs && renderDialogs()}
    </>
  );
}
