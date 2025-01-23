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
import { Sync, SyncDetailsData } from "@/components/sync/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SyncProgress } from "@/components/sync/SyncProgress";

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
  modified_by_email: string;
}

// Add interfaces for API responses
interface ConnectionResponse {
  integration_type: string;
  name: string;
  short_name: string;
}

interface DestinationResponse {
  integration_type: string;
  name: string;
  short_name: string;
}

const ViewEditSync = () => {
  const { id } = useParams();1
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [syncDetails, setSyncDetails] = useState<SyncDetailsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [destinationData, setDestinationData] = useState<any>(null);
  const [totalRuns, setTotalRuns] = useState<number>(0);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Fetch sync details
        const syncResponse = await apiClient.get(`/sync/${id}`);
        const syncData: SyncDetails = await syncResponse.json();

        // Fetch source connection
        const sourceConnection = await apiClient.get(`/connections/detail/${syncData.source_connection_id}`);
        const sourceData: ConnectionResponse = await sourceConnection.json();

        // Fetch destination connection
        let destinationData: DestinationResponse;
        if (syncData.destination_connection_id) {
          const destConnection = await apiClient.get(`/connections/detail/${syncData.destination_connection_id}`);
          const destConnectionData = await destConnection.json();
          const destination = await apiClient.get(`/destinations/detail/${destConnectionData.short_name}`);
          destinationData = await destination.json();
        } else {
          // native weaviate
          const destination = await apiClient.get(`/destinations/detail/weaviate_native`);
          destinationData = await destination.json();
        }

        const transformToSyncDetailsData = (
          syncData: SyncDetails,
          source: ConnectionResponse,
          destination: DestinationResponse
        ): SyncDetailsData => ({
          ...syncData,
          createdAt: syncData.created_at,
          modifiedAt: syncData.modified_at,
          cronSchedule: syncData.cron_schedule,
          sourceConnectionId: syncData.source_connection_id,
          destinationConnectionId: syncData.destination_connection_id,
          organizationId: syncData.organization_id,
          createdByEmail: syncData.created_by_email,
          modifiedByEmail: syncData.modified_by_email,
          status: "active",
          totalRuns: totalRuns,
          uiMetadata: {
            source: {
              type: source.integration_type?.toLowerCase() ?? 'Source',
              name: source.name ?? 'Unknown Source',
              shortName: source.short_name ?? 'unknown'
            },
            destination: {
              type: destination.integration_type?.toLowerCase() ?? 'Destination',
              name: destination.name ?? 'Native Airweave',
              shortName: destination.short_name ?? ( destinationData.short_name === 'weaviate_native' ? 'Native' : 'unknown')
            },
            userId: syncData.created_by_email,
            organizationId: syncData.organization_id,
            userEmail: syncData.created_by_email
          }
        });

        const syncDetailsData = transformToSyncDetailsData(syncData, sourceData, destinationData);
        setSyncDetails(syncDetailsData);
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

  const handleJobSelect = (jobId: string) => {
    setSelectedJobId(jobId);
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
      <SyncJobsTable 
        syncId={id || ''} 
        onTotalRunsChange={(total) => setTotalRuns(total)}
        onJobSelect={handleJobSelect}
      />
      
      <Dialog 
        open={!!selectedJobId} 
        onOpenChange={(open) => !open && setSelectedJobId(null)}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Sync Progress</DialogTitle>
          </DialogHeader>
          <SyncProgress 
            syncId={id || null} 
            syncJobId={selectedJobId} 
          />
        </DialogContent>
      </Dialog>
      
      <DeleteSyncDialog 
        open={showDeleteDialog} 
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
      />
    </div>
  );
};

export default ViewEditSync;