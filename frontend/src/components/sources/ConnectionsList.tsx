import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Connection } from "@/types";
import { Search, Plus, Trash2, Database, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { Badge } from "../ui/badge";
import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

interface ConnectionsListProps {
  connections: Connection[];
  search: string;
  onSearchChange: (value: string) => void;
  onConnect: () => void;
}

export function ConnectionsList({
  connections,
  search,
  onSearchChange,
  onConnect,
}: ConnectionsListProps) {
  const [connectionToDelete, setConnectionToDelete] = useState<Connection | null>(null);

  const getStatusIcon = (status: Connection['status']) => {
    switch (status) {
      case 'active':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const handleDelete = async () => {
    if (!connectionToDelete) return;

    try {
      await apiClient.delete(`/connections/${connectionToDelete.id}`);
      toast.success("Connection deleted successfully");
      // You might want to trigger a refresh of the connections list here
    } catch (error) {
      toast.error("Failed to delete connection");
    } finally {
      setConnectionToDelete(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search connections..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button onClick={onConnect} className="bg-primary hover:bg-primary/90">
          <Plus className="h-4 w-4 mr-2" />
          Add New
        </Button>
      </div>

      <ScrollArea className="h-[400px] pr-4">
        <div className="grid gap-4">
          {connections.map((connection) => (
            <div
              key={connection.id}
              className="group relative flex flex-col p-4 border rounded-xl bg-card hover:shadow-md transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-primary" />
                    <span className="font-medium">{connection.name}</span>
                    {getStatusIcon(connection.status)}
                  </div>
                  <code className="text-xs px-2 py-0.5 rounded-md bg-muted">
                    {connection.id}
                  </code>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 text-destructive"
                  onClick={() => setConnectionToDelete(connection)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t">
                <Badge 
                  variant={
                    connection.status === "active" ? "default" : 
                    connection.status === "error" ? "destructive" : 
                    "secondary"
                  }
                >
                  {connection.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Created by: {connection.created_by_email}
                </span>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      <Dialog 
        open={!!connectionToDelete} 
        onOpenChange={(open) => !open && setConnectionToDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Connection</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this connection? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConnectionToDelete(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}