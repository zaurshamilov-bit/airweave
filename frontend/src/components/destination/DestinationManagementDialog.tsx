import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AdvancedVectorSettings } from "./AdvancedVectorSettings";

interface DestinationManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  destination: {
    id: string;
    name: string;
    type: string;
    status: string;
    url: string;
    credentials?: {
      apiKey?: string;
      username?: string;
      password?: string;
    };
  };
}

export function DestinationManagementDialog({
  open,
  onOpenChange,
  destination,
}: DestinationManagementDialogProps) {
  const [name, setName] = useState(destination.name);
  const [showCredentials, setShowCredentials] = useState(false);
  const [showDeleteAlert, setShowDeleteAlert] = useState(false);

  const handleDelete = () => {
    toast.success("Destination deleted successfully");
    setShowDeleteAlert(false);
    onOpenChange(false);
  };

  const handleSave = () => {
    toast.success("Changes saved successfully");
    onOpenChange(false);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <DialogTitle>Manage Destination</DialogTitle>
                <Badge variant={destination.status === "connected" ? "default" : "secondary"}>
                  {destination.status}
                </Badge>
              </div>
            </div>
            <DialogDescription>
              Configure and manage your {destination.type} destination
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="general" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="credentials">Credentials</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
            </TabsList>

            <TabsContent value="general" className="space-y-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter destination name"
                  />
                </div>

                <div className="space-y-2">
                  <Label>URL</Label>
                  <Input value={destination.url} disabled />
                </div>

                <div className="flex justify-end space-x-2">
                  <Button
                    variant="destructive"
                    onClick={() => setShowDeleteAlert(true)}
                    className="w-full sm:w-auto"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Destination
                  </Button>
                  <Button onClick={handleSave} className="w-full sm:w-auto">
                    Save Changes
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="credentials" className="space-y-4">
              <div className="space-y-4">
                {destination.credentials?.apiKey && (
                  <div className="space-y-2">
                    <Label htmlFor="apiKey">API Key</Label>
                    <div className="relative">
                      <Input
                        id="apiKey"
                        type={showCredentials ? "text" : "password"}
                        value={destination.credentials.apiKey}
                        disabled
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-1/2 -translate-y-1/2"
                        onClick={() => setShowCredentials(!showCredentials)}
                      >
                        {showCredentials ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                )}

                {destination.credentials?.username && (
                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      type={showCredentials ? "text" : "password"}
                      value={destination.credentials.username}
                      disabled
                    />
                  </div>
                )}

                {destination.credentials?.password && (
                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showCredentials ? "text" : "password"}
                        value={destination.credentials.password}
                        disabled
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-1/2 -translate-y-1/2"
                        onClick={() => setShowCredentials(!showCredentials)}
                      >
                        {showCredentials ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="advanced">
              <AdvancedVectorSettings />
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showDeleteAlert} onOpenChange={setShowDeleteAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the destination
              and remove all associated data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}