import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Play, Trash2, Settings2 } from "lucide-react";
import { useTheme } from "@/lib/theme-provider";

interface Connection {
  id: string;
  name: string;
  lastSync?: string;
  status: "active" | "inactive" | "error";
}

interface SourceConnectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  shortName: string;
  connections: Connection[];
  onSync: (connectionId: string) => void;
  onDelete: (connectionId: string) => void;
}

export function SourceConnectionDialog({
  open,
  onOpenChange,
  name,
  shortName,
  connections,
  onSync,
  onDelete,
}: SourceConnectionDialogProps) {
  const { resolvedTheme } = useTheme();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 flex items-center justify-center">
              <img 
                src={getAppIconUrl(shortName, resolvedTheme)} 
                alt={`${name} icon`}
                className="w-6 h-6"
              />
            </div>
            <div>
              <DialogTitle>Manage {name} Connections</DialogTitle>
              <DialogDescription>
                View and manage your existing {name} connections
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <Tabs defaultValue="connections" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="connections">Connections</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="connections">
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-4">
                {connections.map((connection) => (
                  <div
                    key={connection.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="space-y-1">
                      <div className="font-medium">{connection.name}</div>
                      {connection.lastSync && (
                        <div className="text-sm text-muted-foreground">
                          Last sync: {connection.lastSync}
                        </div>
                      )}
                      <Badge 
                        variant={
                          connection.status === "active" ? "default" : 
                          connection.status === "error" ? "destructive" : 
                          "secondary"
                        }
                      >
                        {connection.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onSync(connection.id)}
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                      >
                        <Settings2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDelete(connection.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="settings">
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="font-medium">Global Settings</h3>
                <p className="text-sm text-muted-foreground">
                  Configure settings that apply to all connections for this source.
                </p>
              </div>
              {/* Add global settings controls here */}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}