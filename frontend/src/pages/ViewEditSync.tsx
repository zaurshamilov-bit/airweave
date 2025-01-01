import { useState } from "react";
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

// Mock data - replace with actual API calls
const mockSyncDetails = {
  id: "sync_123",
  name: "Daily Notion Sync",
  description: "Synchronizes Notion workspace daily",
  createdAt: "2024-03-20T10:00:00Z",
  updatedAt: "2024-03-21T15:30:00Z",
  totalRuns: 45,
  status: "active",
  schedule: "Daily at 2 AM",
  metadata: {
    userId: "user_789",
    organizationId: "org_456",
    source: {
      type: "notion",
      name: "Notion Workspace",
      icon: "/icons/notion.svg"
    },
    destination: {
      type: "weaviate",
      name: "Production Vector DB",
      icon: "/icons/weaviate.svg"
    }
  }
};

const mockSyncJobs = [
  {
    id: "job_1",
    startTime: "2024-03-21T02:00:00Z",
    endTime: "2024-03-21T02:15:00Z",
    status: "completed",
    itemsAdded: 102,
    itemsDeleted: 8,
    itemsUnchanged: 489,
    error: null
  },
  {
    id: "job_2",
    startTime: "2024-03-20T02:00:00Z",
    endTime: "2024-03-20T02:12:00Z",
    status: "completed",
    itemsAdded: 45,
    itemsDeleted: 12,
    itemsUnchanged: 234,
    error: null
  }
];

const ViewEditSync = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const handleDelete = () => {
    // API call would go here
    toast({
      title: "Synchronization deleted",
      description: "The synchronization has been permanently deleted."
    });
    navigate("/sync/schedule");
  };

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
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
            <h1 className="text-3xl font-bold">{mockSyncDetails.name}</h1>
            <p className="text-muted-foreground mt-1">
              {mockSyncDetails.description}
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
            {format(new Date(mockSyncDetails.createdAt), "MMM d, yyyy")}
          </p>
        </Card>
        <Card className="p-6 space-y-2">
          <div className="flex items-center text-muted-foreground">
            <Activity className="mr-2 h-4 w-4" />
            Total Runs
          </div>
          <p className="text-2xl font-semibold">{mockSyncDetails.totalRuns}</p>
        </Card>
        <Card className="p-6 space-y-2">
          <div className="flex items-center text-muted-foreground">
            <Clock className="mr-2 h-4 w-4" />
            Schedule
          </div>
          <p className="text-2xl font-semibold">{mockSyncDetails.schedule}</p>
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
              <p className="font-medium">{mockSyncDetails.metadata.source.name}</p>
              <p className="text-sm text-muted-foreground">Source</p>
            </div>
          </div>
          <ArrowRight className="h-6 w-6 text-muted-foreground" />
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-lg bg-secondary flex items-center justify-center">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <p className="font-medium">{mockSyncDetails.metadata.destination.name}</p>
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
              {mockSyncJobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>
                    {format(new Date(job.startTime), "MMM d, yyyy HH:mm")}
                  </TableCell>
                  <TableCell>
                    {format(
                      new Date(job.endTime).getTime() - new Date(job.startTime).getTime(),
                      "m"
                    )}m
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
                      +{job.itemsAdded} -{job.itemsDeleted} ={job.itemsUnchanged}
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