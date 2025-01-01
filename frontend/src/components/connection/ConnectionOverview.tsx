import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RefreshCcw } from "lucide-react";
import { toast } from "sonner";

interface ConnectionOverviewProps {
  lastSyncTime?: string;
  onSync: () => void;
}

export function ConnectionOverview({ lastSyncTime = "2 hours ago", onSync }: ConnectionOverviewProps) {
  const handleSync = () => {
    onSync();
    toast.success("Sync started successfully");
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">Connection Details</h4>
            <p className="text-sm text-muted-foreground">
              View and manage your connection settings
            </p>
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label>Connection Status</Label>
                <div className="text-sm text-muted-foreground">
                  Last synced: {lastSyncTime}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={handleSync}
              >
                <RefreshCcw className="h-4 w-4" />
                Sync Now
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <div className="space-y-2">
          <h4 className="font-medium leading-none">Recent Activity</h4>
          <p className="text-sm text-muted-foreground">
            View your recent sync activity
          </p>
        </div>
        <div className="grid gap-2">
          <div className="rounded-lg border p-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="font-medium">Successful Sync</div>
                <div className="text-sm text-muted-foreground">2h ago</div>
              </div>
              <div className="text-sm text-muted-foreground">
                Successfully synced 150 documents
              </div>
            </div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="font-medium">Successful Sync</div>
                <div className="text-sm text-muted-foreground">6h ago</div>
              </div>
              <div className="text-sm text-muted-foreground">
                Successfully synced 75 documents
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}