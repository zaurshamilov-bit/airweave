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
import { useState } from "react";
import { Connection } from "@/types";
import { getAppIconUrl } from "@/lib/utils/icons";
import { ConnectionsList } from "./ConnectionsList";
import { useTheme } from "@/lib/theme-provider";

interface ManageSourceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  shortName: string;
  description: string;
  onConnect: () => void;
  existingConnections?: Connection[];
  isLoading?: boolean;
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
}: ManageSourceDialogProps) {
  const [search, setSearch] = useState("");
  const [selectedTab, setSelectedTab] = useState("information");
  const { resolvedTheme } = useTheme();

  const filteredConnections = existingConnections.filter(conn => 
    conn.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
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
              <DialogTitle>{name}</DialogTitle>
              <DialogDescription>Manage your {name} integration</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <Tabs value={selectedTab} onValueChange={setSelectedTab} className="mt-4">
          <TabsList className="grid w-full grid-cols-2 h-12">
            <TabsTrigger value="information" className="text-sm">Information</TabsTrigger>
            <TabsTrigger value="connections" className="text-sm">Connections</TabsTrigger>
            {/* TODO: Add settings tab once we have settings */}
            {/* <TabsTrigger value="settings" className="text-sm">Settings</TabsTrigger> */}
          </TabsList>

          <TabsContent value="information" className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold mb-2">Overview</h3>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2">Features</h3>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">Full Text Search</Badge>
                <Badge variant="secondary">Real-time Sync</Badge>
                <Badge variant="secondary">Metadata Extraction</Badge>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2">Data Types</h3>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                <li>Documents and Files</li>
                <li>Text Content</li>
                <li>Metadata</li>
                <li>User Information</li>
              </ul>
            </div>
          </TabsContent>

          <TabsContent value="connections">
            <ConnectionsList
              connections={filteredConnections}
              search={search}
              onSearchChange={setSearch}
              onConnect={onConnect}
            />
          </TabsContent>
{/* 
          <TabsContent value="settings" className="space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="font-medium mb-2">Sync Settings</h3>
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Default Sync Interval</label>
                    <Input type="number" placeholder="30" />
                    <p className="text-sm text-muted-foreground">Minutes between automatic syncs</p>
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Batch Size</label>
                    <Input type="number" placeholder="100" />
                    <p className="text-sm text-muted-foreground">Number of items to process in each sync batch</p>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-medium mb-2">Data Processing</h3>
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Content Types</label>
                    <Input placeholder="pdf,doc,txt" />
                    <p className="text-sm text-muted-foreground">Comma-separated list of file extensions to process</p>
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Excluded Paths</label>
                    <Input placeholder="/temp,/archive" />
                    <p className="text-sm text-muted-foreground">Paths to exclude from syncing</p>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent> */}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}