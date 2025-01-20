import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncMetadata } from "@/components/sync/SyncMetadata";
import { SyncPipelineVisual } from "@/components/sync/SyncPipelineVisual";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "sonner";
import { apiClient } from "@/config/api";

interface Sync {
  id: string;
  name: string;
  description: string;
  status: string;
  schedule: string;
  white_label_id: string;
  source_id: string;
  destination_id: string;
  created_at: string;
  modified_at: string;
  created_by_email: string;
  modified_by_email: string;
  last_run_at?: string;
  next_run_at?: string;
}

const ViewEditWhiteLabelSync = () => {
  const { id, whiteLabelId } = useParams();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [sync, setSync] = useState<Sync | null>(null);

  useEffect(() => {
    const fetchSync = async () => {
      try {
        const response = await apiClient.get(`/white-label/${whiteLabelId}/syncs`);
        if (!response.ok) {
          throw new Error('Failed to fetch sync details');
        }
        const syncs = await response.json();
        const currentSync = syncs.find((s: Sync) => s.id === id);
        if (!currentSync) {
          throw new Error('Sync not found');
        }
        setSync(currentSync);
      } catch (error) {
        toast.error('Failed to load sync details');
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };

    if (whiteLabelId && id) {
      fetchSync();
    }
  }, [whiteLabelId, id]);

  const handleDelete = async () => {
    try {
      const response = await apiClient.delete(`/sync/${id}`);
      if (!response.ok) {
        throw new Error('Failed to delete sync');
      }
      toast.success("Synchronization deleted successfully");
      navigate(`/white-label/${whiteLabelId}`);
    } catch (error) {
      toast.error('Failed to delete sync');
      console.error(error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!sync) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center text-muted-foreground">
          Sync not found
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(`/white-label/${whiteLabelId}`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{sync.name}</h1>
            <p className="text-muted-foreground mt-1">
              {sync.description}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline"
            onClick={() => navigate(`/sync/${id}/edit`)}
          >
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

      <Card className="p-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h3 className="font-medium text-sm text-muted-foreground">Status</h3>
            <p className="mt-1">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                sync.status === "active" 
                  ? "bg-green-100 text-green-800" 
                  : "bg-yellow-100 text-yellow-800"
              }`}>
                {sync.status}
              </span>
            </p>
          </div>
          <div>
            <h3 className="font-medium text-sm text-muted-foreground">Schedule</h3>
            <p className="mt-1">{sync.schedule}</p>
          </div>
          <div>
            <h3 className="font-medium text-sm text-muted-foreground">Last Run</h3>
            <p className="mt-1">{sync.last_run_at ? new Date(sync.last_run_at).toLocaleString() : 'Never'}</p>
          </div>
          <div>
            <h3 className="font-medium text-sm text-muted-foreground">Next Run</h3>
            <p className="mt-1">{sync.next_run_at ? new Date(sync.next_run_at).toLocaleString() : 'Not scheduled'}</p>
          </div>
        </div>
      </Card>

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