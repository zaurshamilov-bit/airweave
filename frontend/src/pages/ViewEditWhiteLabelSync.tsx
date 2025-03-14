import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import { ArrowLeft, Calendar, Clock, Database, Edit2, Trash2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncMetadata } from "@/components/sync/SyncMetadata";
import { SyncPipelineVisual } from "@/components/sync/SyncPipelineVisual";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "sonner";

// Mock data - replace with actual API calls
const mockWhiteLabelSyncDetails = {
  id: "sync_123",
  name: "Daily Slack Sync",
  description: "Synchronizes Slack workspace daily",
  createdAt: "2024-03-20T10:00:00Z",
  updatedAt: "2024-03-21T15:30:00Z",
  totalRuns: 45,
  status: "active",
  schedule: "Daily at 2 AM",
  whiteLabelInfo: {
    name: "Neena White Label for Slack",
    clientId: "client_123456",
    clientSecret: "secret_abcdef",
  },
  metadata: {
    userId: "user_789",
    organizationId: "org_456",
    email: "orhanrauf@gmail.com",
    source: {
      type: "slack",
      name: "Slack Workspace",
      shortName: "slack"
    },
    destination: {
      type: "weaviate",
      name: "Production Vector DB",
      shortName: "weaviate"
    }
  }
};

const ViewEditWhiteLabelSync = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const handleDelete = () => {
    toast.success("Synchronization deleted successfully");
    navigate("/sync/schedule");
  };

  return (
    <div className="container mx-auto pb-8 space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sync/schedule")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{mockWhiteLabelSyncDetails.name}</h1>
            <p className="text-muted-foreground mt-1">
              {mockWhiteLabelSyncDetails.description}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Edit2 className="mr-2 h-4 w-4" />
            Edit
          </Button>
          <Button
            variant="destructive"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <SyncMetadata sync={mockWhiteLabelSyncDetails} />
      <SyncPipelineVisual sync={mockWhiteLabelSyncDetails} />
      <SyncJobsTable syncId={id || ''} />
      <DeleteSyncDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
      />
    </div>
  );
};

export default ViewEditWhiteLabelSync;
