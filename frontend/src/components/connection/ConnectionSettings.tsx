import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

interface ConnectionSettingsProps {
  onDelete: () => void;
}

export function ConnectionSettings({ onDelete }: ConnectionSettingsProps) {
  const [autoSync, setAutoSync] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = () => {
    setIsDeleting(true);
    setTimeout(() => {
      setIsDeleting(false);
      onDelete();
      toast.success("Connection deleted successfully");
    }, 1000);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">Sync Settings</h4>
            <p className="text-sm text-muted-foreground">
              Configure how your data is synced
            </p>
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label>Automatic Sync</Label>
                <div className="text-sm text-muted-foreground">
                  Sync your data automatically every hour
                </div>
              </div>
              <Switch checked={autoSync} onCheckedChange={setAutoSync} />
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none text-destructive">
              Danger Zone
            </h4>
            <p className="text-sm text-muted-foreground">
              Manage your connection settings
            </p>
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between rounded-lg border border-destructive p-4">
              <div className="space-y-0.5">
                <Label>Delete Connection</Label>
                <div className="text-sm text-muted-foreground">
                  This action cannot be undone
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  "Deleting..."
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}