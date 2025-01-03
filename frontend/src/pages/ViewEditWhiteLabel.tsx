import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Eye, EyeOff, ArrowLeft, Trash2 } from "lucide-react";
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
import { toast } from "sonner";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";

interface SyncPipeline {
  id: string;
  name: string;
  status: "active" | "inactive";
  lastSync: string;
  nextSync: string;
}

const ViewEditWhiteLabel = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showSecret, setShowSecret] = useState(false);
  const [showDeleteAlert, setShowDeleteAlert] = useState(false);

  // Mock data - in a real app this would come from your API
  const integration = {
    id: id,
    name: "Customer Portal Integration",
    clientId: "client_123456",
    clientSecret: "secret_abcdef",
    frontendUrl: "https://customer.example.com/callback",
    source: "asana",
  };

  const syncPipelines: SyncPipeline[] = [
    {
      id: "sync_1",
      name: "Daily Tasks Sync",
      status: "active",
      lastSync: "2024-03-20 14:30",
      nextSync: "2024-03-21 14:30",
    },
    {
      id: "sync_2",
      name: "Weekly Projects Sync",
      status: "inactive",
      lastSync: "2024-03-19 10:00",
      nextSync: "2024-03-26 10:00",
    },
  ];

  const handleDelete = () => {
    // API call would go here
    toast.success("Integration deleted successfully");
    navigate("/white-label");
  };

  const handleSave = () => {
    // API call would go here
    toast.success("Changes saved successfully");
  };

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/white-label")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Edit Integration</h1>
          <p className="text-muted-foreground mt-2">
            Manage your OAuth2 integration settings
          </p>
        </div>
      </div>

      <Card className="p-6 space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Integration Name</Label>
            <Input
              id="name"
              defaultValue={integration.name}
              placeholder="Enter integration name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="clientId">Client ID</Label>
            <Input
              id="clientId"
              defaultValue={integration.clientId}
              placeholder="Enter client ID"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="clientSecret">Client Secret</Label>
            <div className="relative">
              <Input
                id="clientSecret"
                type={showSecret ? "text" : "password"}
                defaultValue={integration.clientSecret}
                placeholder="Enter client secret"
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setShowSecret(!showSecret)}
              >
                {showSecret ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="frontendUrl">Frontend Callback URL</Label>
            <Input
              id="frontendUrl"
              defaultValue={integration.frontendUrl}
              placeholder="Enter frontend callback URL"
            />
          </div>

          <div className="flex justify-between pt-4">
            <Button
              variant="destructive"
              onClick={() => setShowDeleteAlert(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Integration
            </Button>
            <Button onClick={handleSave}>Save Changes</Button>
          </div>
        </div>
      </Card>

      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Sync Pipelines</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Sync</TableHead>
                <TableHead>Next Sync</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncPipelines.map((pipeline) => (
                <TableRow
                  key={pipeline.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/sync/${pipeline.id}`)}
                >
                  <TableCell>{pipeline.name}</TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        pipeline.status === "active"
                          ? "bg-green-100 text-green-800"
                          : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {pipeline.status}
                    </span>
                  </TableCell>
                  <TableCell>{pipeline.lastSync}</TableCell>
                  <TableCell>{pipeline.nextSync}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      <AlertDialog open={showDeleteAlert} onOpenChange={setShowDeleteAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the
              integration and remove all associated sync pipelines.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ViewEditWhiteLabel;