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
  ArrowRight,
  Activity
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Fetch sync details
        const syncResponse = await apiClient.get(`/sync/${id}`);
        const syncData: SyncDetails = await syncResponse.json();

        // Fetch source connection
        const sourceConnection = await apiClient.get(`/connections/list/source`);
        const sourceData = await sourceConnection.json();
        const source = sourceData.find(
          (conn: any) => conn.id === syncData.source_connection_id
        );

        // Fetch destination connection
        const destConnection = await apiClient.get(`/connections/list/destination`);
        const destData = await destConnection.json();
        const destination = destData.find(
          (conn: any) => conn.id === syncData.destination_connection_id
        );

        // Fetch sync jobs
        const jobsResponse = await apiClient.get(`/sync/${id}/jobs`);
        const jobsData: SyncJob[] = await jobsResponse.json();

        // Transform data to match your UI structure
        setSyncDetails({
          id: syncData.id,
          name: syncData.name,
          description: syncData.description,
          createdAt: syncData.created_at,
          updatedAt: syncData.modified_at,
          totalRuns: jobsData.length,
          status: "active", // You might want to derive this from the sync state
          schedule: syncData.cron_schedule, // You might want to make this human readable
          metadata: {
            userId: syncData.created_by_email,
            organizationId: syncData.organization_id,
            source: source ? {
              type: source.integration_type?.toLowerCase(),
              name: source.name,
              icon: `/icons/${source.short_name}.svg`
            } : null,
            destination: destination ? {
              type: destination.integration_type?.toLowerCase(),
              name: destination.name,
              icon: `/icons/${destination.short_name}.svg`
            } : null
          }
        });

        setSyncJobs(jobsData);
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
        title: "Synchronization deleted",
        description: "The synchronization has been permanently deleted."
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
    return <div>Loading...</div>; // You might want to use a proper loading component
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
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

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-6 space-y-2">
          <div className="flex items-center text-muted-foreground">
            <Calendar className="mr-2 h-4 w-4" />
            Created
          </div>
          <p className="text-2xl font-semibold">
            {syncDetails?.createdAt ? format(new Date(syncDetails.createdAt), "MMM d, yyyy") : "-"}
          </p>
        </Card>
        <Card className="p-6 space-y-2">
          <div className="flex items-center text-muted-foreground">
            <Activity className="mr-2 h-4 w-4" />
            Total Runs
          </div>
          <p className="text-2xl font-semibold">{syncDetails?.totalRuns}</p>
        </Card>
        <Card className="p-6 space-y-2">
          <div className="flex items-center text-muted-foreground">
            <Clock className="mr-2 h-4 w-4" />
            Schedule
          </div>
          <p className="text-2xl font-semibold">{syncDetails?.schedule}</p>
        </Card>
      </div>

      {/* Source and Destination */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-6">Pipeline Configuration</h2>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-lg bg-secondary flex items-center justify-center">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <p className="font-medium">{syncDetails?.metadata.source?.name}</p>
              <p className="text-sm text-muted-foreground">Source</p>
            </div>
          </div>
          <ArrowRight className="h-6 w-6 text-muted-foreground" />
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-lg bg-secondary flex items-center justify-center">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <p className="font-medium">{syncDetails?.metadata.destination?.name}</p>
              <p className="text-sm text-muted-foreground">Destination</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Sync Jobs Table */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Sync History</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Start Time</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Changes</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syncJobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>
                    {job.start_time ? format(new Date(job.start_time), "MMM d, yyyy HH:mm") : "-"}
                  </TableCell>
                  <TableCell>
                    {job.end_time && job.start_time ? 
                      `${Math.round((new Date(job.end_time).getTime() - new Date(job.start_time).getTime()) / 60000)}m` 
                      : "-"}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        job.status === "completed"
                          ? "bg-green-100 text-green-800"
                          : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {job.status}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">
                      +{job.items_added} -{job.items_deleted} ={job.items_unchanged}
                    </span>
                  </TableCell>
                  <TableCell>{job.error || "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this synchronization and all its history.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Sync
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ViewEditSync;