import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import { 
  ArrowLeft, 
  Calendar, 
  Clock, 
  Database, 
  Edit2, 
  Trash2,
  ArrowRight 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncMetadata } from "@/components/sync/SyncMetadata";
import { SyncPipelineVisual } from "@/components/sync/SyncPipelineVisual";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";

interface SyncJob {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  items_added: number;
  items_deleted: number;
  items_unchanged: number;
  error: string | null;
}

interface SyncDetails {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  modified_at: string;
  cron_schedule: string | null;
  created_by_email: string;
  organization_id: string;
  source_connection_id: string;
  destination_connection_id: string;
}

const ViewEditSync = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [syncDetails, setSyncDetails] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [destinationData, setDestinationData] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Fetch sync details
        const syncResponse = await apiClient.get(`/sync/${id}`);
        const syncData: SyncDetails = await syncResponse.json();

        // Fetch source connection
        const sourceConnection = await apiClient.get(`/connections/detail/${syncData.source_connection_id}`);
        const sourceData = await sourceConnection.json();
        const source = sourceData;

        // Fetch destination connection
        if (syncData.destination_connection_id) {
          const destConnection = await apiClient.get(`/connections/detail/${syncData.destination_connection_id}`);
          const destConnectionData = await destConnection.json();
          const destination = await apiClient.get(`/destinations/detail/${destConnectionData.short_name}`);
          const destinationData = await destination.json();
          setDestinationData(destinationData);
        } else {
          // native weaviate
          const destination = await apiClient.get(`/destinations/detail/weaviate_native`);
          const destinationData = await destination.json();
          setDestinationData(destinationData);
        }

        // Transform data to match your UI structure
        setSyncDetails({
          id: syncData.id,
          name: syncData.name,
          description: syncData.description,
          createdAt: syncData.created_at,
          updatedAt: syncData.modified_at,
          status: "active",
          schedule: syncData.cron_schedule,
          metadata: {
            userId: syncData.created_by_email,
            organizationId: syncData.organization_id,
            source: source ? {
              type: source.integration_type?.toLowerCase(),
              name: source.name,
              shortName: source.short_name
            } : null,
            destination: destinationData ? {
              type: destinationData.integration_type?.toLowerCase(),
              name: destinationData.name,
              shortName: destinationData.short_name
            } : null
          }
        });

        setIsLoading(false);
      } catch (error) {
        console.error("Error fetching sync data:", error);
        toast({
          title: "Error",
          description: "Failed to load sync details",
          variant: "destructive"
        });
        setIsLoading(false);
      }
    };

    if (id) {
      fetchData();
    }
  }, [id]);

  const handleDelete = async () => {
    try {
      await apiClient.delete(`/sync/${id}`);
      toast({
        title: "Success",
        description: "Synchronization deleted successfully"
      });
      navigate("/sync");
    } catch (error) {
      console.error("Error deleting sync:", error);
      toast({
        title: "Error",
        description: "Failed to delete synchronization",
        variant: "destructive"
      });
    }
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sync")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{syncDetails?.name}</h1>
            <p className="text-muted-foreground mt-1">
              {syncDetails?.description}
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

      <SyncMetadata sync={syncDetails} />
      <SyncPipelineVisual sync={syncDetails} />
      <SyncJobsTable syncId={id || ''} />
      <DeleteSyncDialog 
        open={showDeleteDialog} 
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
      />
    </div>
  );
};

export default ViewEditSync;