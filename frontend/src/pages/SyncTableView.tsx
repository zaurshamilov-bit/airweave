import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Search, Plus, Calendar, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { format, formatRelative, parseISO } from "date-fns";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

// Define types based on backend schemas
interface Sync {
  id: string;
  name: string;
  cron_schedule: string | null;
  created_at: string;
  white_label_id: string | null;
  white_label_user_identifier: string | null;
}

interface SyncJob {
  id: string;
  sync_id: string;
  sync_name: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  stats: {
    processed_items: number;
    total_items: number;
  };
}

type ActiveTab = "syncs" | "jobs";

const SyncTableView = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("syncs");
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [syncs, setSyncs] = useState<Sync[]>([]);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isJobsLoading, setIsJobsLoading] = useState(true);
  const [syncToDelete, setSyncToDelete] = useState<Sync | null>(null);
  const [deleteData, setDeleteData] = useState(false);

  // Fetch syncs
  useEffect(() => {
    const fetchSyncs = async () => {
      try {
        const response = await apiClient.get("/sync/");
        const data = await response.json();
        setSyncs(data);
      } catch (error) {
        toast.error("Failed to fetch syncs");
      } finally {
        setIsLoading(false);
      }
    };

    fetchSyncs();
  }, []);

  // Fetch sync jobs
  useEffect(() => {
    const fetchSyncJobs = async () => {
      try {
        const response = await apiClient.get("/sync/jobs");
        const data = await response.json();
        setSyncJobs(data);
      } catch (error) {
        toast.error("Failed to fetch sync jobs");
      } finally {
        setIsJobsLoading(false);
      }
    };

    fetchSyncJobs();
  }, []);

  // Update delete handler
  const handleDeleteSync = async (sync: Sync) => {
    setSyncToDelete(sync);
  };

  const confirmDelete = async () => {
    if (!syncToDelete) return;

    try {
      await apiClient.delete(`/sync/${syncToDelete.id}?delete_data=${deleteData}`);
      setSyncs(syncs.filter(sync => sync.id !== syncToDelete.id));
      toast.success("Sync deleted successfully");
    } catch (error) {
      toast.error("Failed to delete sync");
    } finally {
      setSyncToDelete(null);
      setDeleteData(false);
    }
  };

  const filteredSyncs = syncs?.filter(sync =>
    sync.name.toLowerCase().includes(search.toLowerCase()) ||
    (sync.cron_schedule || "").toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  const filteredSyncJobs = syncJobs?.filter(job =>
    job.sync_name.toLowerCase().includes(search.toLowerCase()) ||
    job.status.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  // Helper function to format cron schedule
  const formatCronSchedule = (cronSchedule: string | null) => {
    if (!cronSchedule) return "No schedule";
    // This is a simplified example - you might want to use a cron parser library
    return cronSchedule;
  };

  // Helper function for date formatting
  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = parseISO(dateStr);
    const formattedDate = formatRelative(date, new Date());
    // Capitalize first letter and format time if it's today/yesterday
    const formatted = formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1);

    // If it's today/yesterday, append the time
    if (formatted.startsWith('Today') || formatted.startsWith('Yesterday')) {
      return `${formatted} at ${format(date, 'HH:mm')}`;
    }

    return formatted;
  };

  // Get status badge for sync jobs
  const getStatusBadge = (status: string) => {
    let bgColor = "";
    let textColor = "";

    switch (status) {
      case "running":
        bgColor = "bg-blue-100 dark:bg-blue-900/40";
        textColor = "text-blue-800 dark:text-blue-300";
        break;
      case "completed":
        bgColor = "bg-green-100 dark:bg-green-900/40";
        textColor = "text-green-800 dark:text-green-300";
        break;
      case "failed":
        bgColor = "bg-red-100 dark:bg-red-900/40";
        textColor = "text-red-800 dark:text-red-300";
        break;
      case "pending":
        bgColor = "bg-yellow-100 dark:bg-yellow-900/40";
        textColor = "text-yellow-800 dark:text-yellow-300";
        break;
      default:
        bgColor = "bg-gray-100 dark:bg-gray-800";
        textColor = "text-gray-800 dark:text-gray-300";
    }

    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${bgColor} ${textColor}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  return (
    <div className="container mx-auto pb-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Synchronizations</h1>
          <p className="text-muted-foreground mt-2">
            View and manage your synchronization history
          </p>
        </div>
      </div>

      <div className="flex space-x-1 p-1 rounded-md mb-4 w-fit">
        <Button
          variant={activeTab === "syncs" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("syncs")}
          className={cn(
            "rounded-sm text-sm",
            activeTab === "syncs"
              ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
              : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
          )}
        >
          Syncs
        </Button>
        <Button
          variant={activeTab === "jobs" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("jobs")}
          className={cn(
            "rounded-sm text-sm",
            activeTab === "jobs"
              ? "shadow-sm bg-slate-200 dark:bg-muted hover:bg-slate-200 dark:hover:bg-muted hover:text-foreground text-foreground"
              : "hover:bg-slate-200/60 dark:hover:bg-muted/60 hover:text-foreground"
          )}
        >
          Sync Jobs
        </Button>
      </div>
      <div className="bg-background rounded-lg border">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={`Search ${activeTab === "syncs" ? "synchronizations" : "sync jobs"}...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {activeTab === "syncs" ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Schedule</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>White Label</TableHead>
                <TableHead className="w-[50px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center pb-8">
                    <div className="flex items-center justify-center text-muted-foreground">
                      Loading...
                    </div>
                  </TableCell>
                </TableRow>
              ) : filteredSyncs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center pb-8">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <p>No synchronizations found</p>
                      <p className="text-sm">Try adjusting your search terms</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredSyncs.map((sync) => (
                  <TableRow
                    key={sync.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest('button')) return;
                      navigate(`/sync/${sync.id}`);
                    }}
                  >
                    <TableCell className="font-medium">{sync.name}</TableCell>
                    <TableCell>{formatCronSchedule(sync.cron_schedule)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(sync.created_at)}
                    </TableCell>
                    <TableCell>
                      {sync.white_label_id ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                          {sync.white_label_user_identifier}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSync(sync);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sync Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead>Progress</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isJobsLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center pb-8">
                    <div className="flex items-center justify-center text-muted-foreground">
                      Loading...
                    </div>
                  </TableCell>
                </TableRow>
              ) : filteredSyncJobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center pb-8">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <p>No sync jobs found</p>
                      <p className="text-sm">Try adjusting your search terms</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredSyncJobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={() => navigate(`/sync/${job.sync_id}/job/${job.id}`)}
                  >
                    <TableCell className="font-medium">{job.sync_name}</TableCell>
                    <TableCell>{getStatusBadge(job.status)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(job.started_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(job.completed_at)}
                    </TableCell>
                    <TableCell>
                      {job.stats ? (
                        <div className="flex items-center space-x-2">
                          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                            <div
                              className="bg-primary h-2.5 rounded-full"
                              style={{
                                width: `${job.stats.total_items > 0
                                  ? Math.min(Math.round((job.stats.processed_items / job.stats.total_items) * 100), 100)
                                  : 0}%`
                              }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {job.stats.processed_items}/{job.stats.total_items}
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog
        open={!!syncToDelete}
        onOpenChange={(open) => {
          if (!open) {
            setSyncToDelete(null);
            setDeleteData(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-xl">Delete Sync</DialogTitle>
            <DialogDescription className="pt-3">
              Are you sure you want to delete <span className="font-medium text-foreground">{syncToDelete?.name}</span>?
              <p className="mt-2 text-destructive dark:text-red-400">This action cannot be undone.</p>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="items-top flex space-x-2">
              <Checkbox
                id="delete-data"
                checked={deleteData}
                onCheckedChange={(checked) => setDeleteData(checked as boolean)}
                className="mt-1"
              />
              <div className="grid gap-1.5 leading-none">
                <Label
                  htmlFor="delete-data"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Delete associated data
                </Label>
                <p className="text-sm text-muted-foreground">
                  This will permanently remove all synchronized data from the destination
                </p>
              </div>
            </div>
            {deleteData && (
              <div className="flex items-center space-x-2 text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/50 rounded-md p-3">
                <AlertCircle className="h-4 w-4" />
                <p className="text-xs">
                  Warning: This will delete all data in the destination that was created by this sync
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setSyncToDelete(null);
                setDeleteData(false);
              }}
              className="w-full sm:w-auto"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              className="w-full sm:w-auto"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SyncTableView;
