import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConnectionOverview } from "./connection/ConnectionOverview";
import { ConnectionSettings } from "./connection/ConnectionSettings";

interface ManageConnectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  type: "source" | "destination";
  extraContent?: React.ReactNode;
}

export function ManageConnectionDialog({
  open,
  onOpenChange,
  title,
  description,
  type,
  extraContent,
}: ManageConnectionDialogProps) {
  const handleSync = () => {
    // Sync logic here
  };

  const handleDelete = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DialogTitle>{title}</DialogTitle>
              <Badge variant="secondary" className="h-6">
                Connected
              </Badge>
            </div>
          </div>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <ConnectionOverview onSync={handleSync} />
            {extraContent}
          </TabsContent>

          <TabsContent value="settings">
            <ConnectionSettings onDelete={handleDelete} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}