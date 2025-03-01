import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Info, ChevronDown, Check } from "lucide-react";
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
import { useToast } from "@/components/ui/use-toast";
import { apiClient } from "@/lib/api";
import { AddSourceWizard } from "./AddSourceWizard";
import { useTheme } from "@/lib/theme-provider";

interface Connection {
  id: string;
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

interface SyncDataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onSelect: (connectionId: string) => void;
  connections?: Connection[];
  authType?: string | null;
}

export function SyncDataSourceCard({ 
  shortName, 
  name, 
  description, 
  status, 
  onSelect,
  connections = [],
  authType,
}: SyncDataSourceCardProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const { toast } = useToast();
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const sortedConnections = [...connections].sort((a, b) => 
      new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
    );
    setSelectedConnectionId(sortedConnections[0]?.id || null);
  }, [connections]);

  const initiateOAuth = async () => {
    try {
      const resp = await apiClient.get(`/connections/oauth2/source/auth_url?short_name=${shortName}`);

      if (!resp.ok) {
        throw new Error("Failed to retrieve auth URL");
      }

      // Get the auth URL and remove any quotes
      const authUrl = await resp.text();
      const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes
      
      // Log for debugging
      console.log("Redirecting to:", cleanUrl);
      
      // Redirect to the cleaned OAuth provider URL
      window.location.href = cleanUrl;
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Failed to initiate OAuth2",
        description: err.message ?? String(err),
      });
    }
  };

  const handleConnectionSelect = (connectionId: string) => {
    setSelectedConnectionId(connectionId);
    setOpen(false);
    onSelect(connectionId);
  };

  const handleChooseSource = () => {
    if (status === "connected" && selectedConnectionId) {
      onSelect(selectedConnectionId);
    } else {
      handleConnect();
    }
  };

  const handleConnect = async () => {
    if (authType === "none" || authType?.startsWith("basic") || authType?.startsWith("api_key")) {
      setShowWizard(true);
    } else if (authType?.startsWith("oauth2")) {
      await initiateOAuth();
    } else {
      // Default to wizard for unknown auth types
      setShowWizard(true);
    }
  };

  const handleWizardComplete = (connectionId: string) => {
    setSelectedConnectionId(connectionId);
    onSelect(connectionId);
  };

  const handleAddNewConnection = () => {
    if (authType?.startsWith("oauth2")) {
      initiateOAuth();
    } else {
      setShowWizard(true);
    }
    setOpen(false);
  };

  return (
    <>
      <Card className={cn(
        "w-full min-h-[240px] flex flex-col justify-between overflow-hidden"
      )}>
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
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Info className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Click to learn more about this source</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-0 flex-grow">
          <p className="text-sm text-muted-foreground line-clamp-3">
            Extract and sync your {name} data to your vector database of choice.
          </p>
        </CardContent>
        <CardFooter className="p-4 pt-0">
          <div className="flex w-full gap-1">
            <Button 
              onClick={handleChooseSource}
              variant={status === "connected" ? "secondary" : "default"}
              className="flex-1"
            >
              {status === "connected" ? "Choose Source" : "Connect"}
            </Button>
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
          </div>
        </CardFooter>
      </Card>

      {showWizard && (
        <AddSourceWizard
          open={showWizard}
          onOpenChange={setShowWizard}
          onComplete={handleWizardComplete}
          shortName={shortName}
          name={name}
        />
      )}
    </>
  );
}