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
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Connection } from "@/types";
import { getAppIconUrl } from "@/lib/utils/icons";
import { ConnectionsList } from "./ConnectionsList";
import { Trash2, AlertCircle } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { apiClient } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";

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
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteData, setDeleteData] = useState(false);
  const { toast } = useToast();

  const filteredConnections = existingConnections.filter(conn => 
    conn.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleDelete = async () => {
    try {
      // Assuming you have an endpoint to delete the source and its connections
      await apiClient.delete(`/connections/source/${shortName}?delete_data=${deleteData}`);
      toast({
        title: "Success",
        description: "Source and connections deleted successfully",
      });
      onOpenChange(false);
      // You might want to trigger a refresh of the parent component here
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete source and connections",
        variant: "destructive",
      });
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <img 
                  src={getAppIconUrl(shortName)} 
                  alt={`${name} icon`}
                  className="w-8 h-8"
                />
                <div>
                  <DialogTitle>{name}</DialogTitle>
                  <DialogDescription>Manage your {name} integration</DialogDescription>
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteDialog(true)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Source
              </Button>
            </div>
          </DialogHeader>

          <Tabs value={selectedTab} onValueChange={setSelectedTab} className="mt-4">
            <TabsList className="grid w-full grid-cols-2 h-12">
              <TabsTrigger value="information" className="text-sm">Information</TabsTrigger>
              <TabsTrigger value="connections" className="text-sm">Connections</TabsTrigger>
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
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Delete Source</DialogTitle>
            <DialogDescription className="pt-3">
              Are you sure you want to delete <span className="font-medium text-foreground">{name}</span>? 
              This will remove all connections associated with this source.
              <p className="mt-2 text-destructive/80">This action cannot be undone.</p>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="items-top flex space-x-2">
              <Checkbox
                id="delete-data"
                checked={deleteData}
                onCheckedChange={(checked) => setDeleteData(checked as boolean)}
                className="mt-1"
              />
              <div className="grid gap-1.5 leading-none">
                <Label
                  htmlFor="delete-data"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Delete associated data
                </Label>
                <p className="text-sm text-muted-foreground">
                  This will permanently remove all synchronized data from the destination
                </p>
              </div>
            </div>
            {deleteData && (
              <div className="flex items-center space-x-2 text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/50 rounded-md p-3">
                <AlertCircle className="h-4 w-4" />
                <p className="text-xs">
                  Warning: This will delete all data in the destination that was created by this source
                </p>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setShowDeleteDialog(false);
                setDeleteData(false);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
            >
              Delete Source
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}