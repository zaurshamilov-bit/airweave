import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { apiClient } from "@/lib/api";
import { getAppIconUrl } from "@/lib/utils/icons";

interface SyncInfo {
  id: string;
  name: string;
  description?: string;
  status?: string;
  source_connection?: {
    short_name: string;
    name: string;
  };
}

interface CreateChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChatCreated: (newChatId: string) => void;
}

export function CreateChatDialog({ open, onOpenChange, onChatCreated }: CreateChatDialogProps) {
  const [syncs, setSyncs] = useState<SyncInfo[]>([]);
  const [syncId, setSyncId] = useState<string>("");
  const [chatName, setChatName] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (open) {
      void loadSyncs();
    }
  }, [open]);

  async function loadSyncs() {
    try {
      setIsLoading(true);
      const resp = await apiClient.get("/sync", {
        with_source_connection: "true",
        skip: 0,
        limit: 100
      });
      
      console.log("API Response:", resp);
      
      const syncData = await resp.json();
      console.log("Processed syncs:", syncData);
      
      setSyncs(syncData.filter(sync => sync.status === 'active').map((sync: any) => ({
        id: sync.id,
        name: sync.name || `Sync ${sync.id}`,
        description: sync.description,
        status: sync.status,
        source_connection: sync.source_connection
      })));
    } catch (err) {
      console.error("Failed to load syncs: ", err);
      if (err.response) {
        console.error("Error response:", err.response.data);
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreateChat() {
    if (!syncId) return;
    
    try {
      setIsLoading(true);
      const resp = await apiClient.post("/chat", {
        name: chatName || "New Chat",
        description,
        sync_id: syncId,
        model_name: "gpt-4", // You might want to make this configurable
        model_settings: {
          temperature: 0.7,
          max_tokens: 1000,
        },
      });
      const chatData = await resp.json();
      onChatCreated(chatData.id);
      onOpenChange(false);
    } catch (err) {
      console.error("Failed to create chat: ", err);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Chat</DialogTitle>
          <DialogDescription>Select a sync and provide optional details, then create your chat.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">


          <div>
            <label className="block text-sm font-medium mb-1">Chat Name</label>
            <Input
              placeholder="Chat Name"
              value={chatName}
              onChange={(e) => setChatName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Sync</label>
            <Select onValueChange={setSyncId} value={syncId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={isLoading ? "Loading syncs..." : "Select a sync..."} />
              </SelectTrigger>
              <SelectContent>
                {syncs.length === 0 && !isLoading && (
                  <SelectItem value="no-syncs" disabled>
                    No syncs available
                  </SelectItem>
                )}
                {syncs.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    <div className="flex items-center gap-2">
                      <img
                        src={getAppIconUrl(s.source_connection?.short_name || 'default')}
                        className="h-4 w-4"
                        alt={s.source_connection?.name || 'Source'}
                      />
                      <span>{s.name}</span>
                      {s.description && (
                        <span className="text-sm text-muted-foreground ml-2">
                          ({s.description})
                        </span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

        </div>
        <div className="mt-4 flex justify-end space-x-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleCreateChat} 
            disabled={!syncId || isLoading}
          >
            {isLoading ? "Creating..." : "Create"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
} 