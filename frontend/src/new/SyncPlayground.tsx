import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import {
    ArrowLeft,
    Calendar,
    Clock,
    Database,
    Edit2,
    Pencil,
    Info,
    Zap,
    Play,
    ExternalLink,
    Eye,
    Copy,
    Activity,
    Box,
    Heart,
    RefreshCw,
    Check,
    X,
    Trash
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncDagEditor } from "@/components/sync/SyncDagEditor";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";
import { Sync, SyncDetailsData } from "@/components/sync/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { SyncProgress } from "@/components/sync/SyncProgress";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl } from "@/lib/utils/icons";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { Input } from "@/components/ui/input";
import { SyncSchedule, SyncScheduleConfig } from "@/components/sync/SyncSchedule";
import "../pages/sync-progress.css"; // Import custom CSS for animations
import { useSyncSubscription } from "@/hooks/useSyncSubscription";

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

interface SyncJob {
    id: string;
    sync_id: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';  // from SyncJobStatus enum
    started_at: string | null;
    completed_at: string | null;
    failed_at: string | null;
    entities_inserted: number;
    entities_updated: number;
    entities_deleted: number;
    entities_kept: number;
    entities_skipped: number;
    error: string | null;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
}

const SyncPlayground = ({ id }: { id: string }) => {
    const navigate = useNavigate();
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [syncDetails, setSyncDetails] = useState<SyncDetailsData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [destinationData, setDestinationData] = useState<any>(null);
    const [totalRuns, setTotalRuns] = useState<number>(0);
    const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
    const [lastSync, setLastSync] = useState<SyncJob | null>(null);
    const [isRunningSync, setIsRunningSync] = useState(false);
    const [totalRuntime, setTotalRuntime] = useState<number | null>(null);
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Name editing state
    const [isEditingName, setIsEditingName] = useState(false);
    const [syncName, setSyncName] = useState("");
    const nameInputRef = useRef<HTMLInputElement>(null);

    // Schedule editing state
    const [showScheduleDialog, setShowScheduleDialog] = useState(false);
    const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
        type: "one-time",
        frequency: "custom"
    });

    const liveUpdates = useSyncSubscription(lastSync?.id);
    const latestUpdate = liveUpdates.length > 0 ? liveUpdates[liveUpdates.length - 1] : null;

    // Derive status from the update flags
    let liveStatus = lastSync?.status;
    if (latestUpdate) {
        if (latestUpdate.is_complete === true) {
            liveStatus = "completed";
        } else if (latestUpdate.is_failed === true) {
            liveStatus = "failed";
        } else {
            // If we have updates but neither complete nor failed, it must be in progress
            liveStatus = "in_progress";
        }
    }

    const status = (liveStatus || lastSync?.status || "").toLowerCase();

    const fetchLastSyncJob = async () => {
        try {
            if (!id) return;

            // Fetch all sync jobs for this sync
            const jobsResponse = await apiClient.get(`/sync/${id}/jobs`);
            if (!jobsResponse.ok) throw new Error("Failed to fetch sync jobs");

            const syncJobs: SyncJob[] = await jobsResponse.json();

            // Sort jobs by created_at date (newest first)
            const sortedJobs = syncJobs.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );

            // Set the most recent job as the last sync
            if (sortedJobs.length > 0) {
                setLastSync(sortedJobs[0]);

                // Calculate total runtime across all completed jobs
                let totalTime = 0;
                syncJobs.forEach(job => {
                    // Use completed_at or failed_at as the end time
                    const endTime = job.completed_at || job.failed_at;
                    if (job.started_at && endTime) {
                        totalTime += new Date(endTime).getTime() - new Date(job.started_at).getTime();
                    }
                });
                setTotalRuntime(totalTime);
            }
        } catch (error) {
            console.error("Error fetching last sync job:", error);
        }
    };

    const refreshData = async () => {
        setIsRefreshing(true);
        try {
            await fetchSyncDetails();
            await fetchLastSyncJob();
        } finally {
            setIsRefreshing(false);
        }
    };

    // Add a function to fetch only the sync details
    const fetchSyncDetails = async () => {
        try {
            if (!id) return;

            // Fetch sync details
            const syncResponse = await apiClient.get(`/sync/${id}`);

            if (!syncResponse.ok) {
                throw new Error("Failed to fetch sync details");
            }

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
                // native qdrant
                const destination = await apiClient.get(`/destinations/detail/qdrant_native`);
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
                status: "active", // You might want to determine this based on actual sync status
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
                        shortName: destination.short_name ?? (destinationData.short_name === 'qdrant_native' ? 'Native' : 'unknown')
                    },
                    userId: syncData.created_by_email,
                    organizationId: syncData.organization_id,
                    userEmail: syncData.created_by_email
                }
            });

            const syncDetailsData = transformToSyncDetailsData(syncData, sourceData, destinationData);
            setSyncDetails(syncDetailsData);

            // Update schedule config based on new data
            setScheduleConfig({
                type: syncData.cron_schedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: syncData.cron_schedule || undefined
            });

        } catch (error) {
            console.error("Error fetching sync details:", error);
            toast({
                title: "Error",
                description: "Failed to refresh sync details",
                variant: "destructive"
            });
        }
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                setIsLoading(true);
                await fetchSyncDetails();
                setIsLoading(false);
                // Fetch last sync job after basic data is loaded
                await fetchLastSyncJob();
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

    useEffect(() => {
        // Set the initial schedule config when syncDetails is loaded
        if (syncDetails) {
            setScheduleConfig({
                type: syncDetails.cronSchedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: syncDetails.cronSchedule || undefined
            });
            if (!isEditingName) {
                setSyncName(syncDetails.name);
            }
        }
    }, [syncDetails, isEditingName]);

    // Add this effect to refresh the lastSync data when a sync completes
    useEffect(() => {
        // When a live sync transitions from running to complete/failed, refresh the job data
        if (latestUpdate && (latestUpdate.is_complete || latestUpdate.is_failed)) {
            // Fetch the latest job data to get accurate stats
            fetchLastSyncJob();
        }
    }, [latestUpdate?.is_complete, latestUpdate?.is_failed]);

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

    const handleEdit = () => {
        navigate(`/sync/${id}/edit`);
    };

    const handleRunSync = async () => {
        try {
            setIsRunningSync(true);
            const response = await apiClient.post(`/sync/${id}/run`);

            if (!response.ok) {
                throw new Error("Failed to start sync job");
            }

            const newJob = await response.json();

            toast({
                title: "Success",
                description: "Sync job started successfully"
            });

            // Update the last sync job immediately
            setLastSync(newJob);
        } catch (error) {
            console.error("Error running sync:", error);
            toast({
                title: "Error",
                description: "Failed to start sync job",
                variant: "destructive"
            });
        } finally {
            setIsRunningSync(false);
        }
    };

    const viewLastSyncJob = () => {
        if (lastSync) {
            // Navigate to the job details page
            navigate(`/sync/${id}/job/${lastSync.id}`);
        }
    };

    // Format milliseconds to human-readable time (days, hours, minutes, seconds)
    const formatTotalRuntime = (ms: number) => {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) {
            return `${days}d ${hours % 24}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    };

    if (isLoading) {
        return <div>Loading...</div>;
    }

    const getNextRunText = () => {
        if (!syncDetails?.cronSchedule) {
            return "Manual trigger";
        }
        // For this example, we're not calculating the actual next run time
        // A proper implementation would parse the cron schedule and calculate the next run
        return `Scheduled (${syncDetails.cronSchedule})`;
    };

    const startEditingName = () => {
        setIsEditingName(true);
        // Set input's initial value to current name only once when starting to edit
        if (nameInputRef.current) {
            nameInputRef.current.value = syncDetails?.name || "";
        }
        setTimeout(() => nameInputRef.current?.focus(), 0);
    };

    const handleSaveNameChange = async () => {
        // Get value directly from input ref instead of state to avoid re-renders during typing
        const newName = nameInputRef.current?.value || "";

        if (!newName.trim() || newName === syncDetails?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/sync/${id}`, { name: newName });
            if (!response.ok) throw new Error("Failed to update sync name");

            // Update local state only after successful API call
            setSyncDetails(prev => prev ? { ...prev, name: newName } : null);
            setIsEditingName(false);

            toast({
                title: "Success",
                description: "Sync name updated successfully"
            });
        } catch (error) {
            console.error("Error updating sync name:", error);
            toast({
                title: "Error",
                description: "Failed to update sync name",
                variant: "destructive"
            });
            setIsEditingName(false);
        }
    };

    // Modify the refreshScheduleData function to remove references to setScheduleText
    const refreshScheduleData = async () => {
        if (!id) return;

        try {
            console.log("Starting schedule refresh");
            // Show loading indicator
            setIsRefreshing(true);

            // Make a targeted API call to get just the sync details
            const response = await apiClient.get(`/sync/${id}`);
            if (!response.ok) throw new Error("Failed to refresh sync data");

            const syncData = await response.json();
            console.log("Got sync data:", syncData);

            // Update the state with the new schedule information
            setSyncDetails(prevDetails => {
                if (!prevDetails) return null;
                console.log("Updating sync details", prevDetails, "with cron_schedule:", syncData.cron_schedule);
                const updated = {
                    ...prevDetails,
                    cronSchedule: syncData.cron_schedule,
                    modifiedAt: syncData.modified_at
                };
                console.log("Updated details:", updated);
                return updated;
            });

            // Update the config state as well
            setScheduleConfig({
                type: syncData.cron_schedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: syncData.cron_schedule || undefined
            });

            toast({
                title: "Success",
                description: "Schedule updated successfully"
            });
        } catch (error) {
            console.error("Error refreshing schedule data:", error);
            toast({
                title: "Error",
                description: "Failed to refresh schedule data",
                variant: "destructive"
            });
        } finally {
            setIsRefreshing(false);
            console.log("Schedule refresh complete");
        }
    };

    return (
        <div className="container mx-auto pb-8 space-y-6 max-w-screen-2xl">

            <div className="space-y-6">


                {/* Live Sync Progress or Final Card */}
                {lastSync && (
                    <div className="w-full flex justify-center my-8">
                        <SyncProgress
                            syncId={id || null}
                            syncJobId={lastSync.id}
                            lastSync={lastSync}
                            isLive={status === "in_progress" || status === "pending"}
                        />
                    </div>
                )}


                {/* Sync Jobs Table */}
                <Card className="border rounded-lg bg-card">
                    <SyncJobsTable
                        syncId={id || ''}
                        onTotalRunsChange={(total) => setTotalRuns(total)}
                        onJobSelect={handleJobSelect}
                    />
                </Card>
            </div>

            {/* Schedule Edit Dialog */}
            <Dialog
                open={showScheduleDialog}
                onOpenChange={(open) => {
                    const wasOpen = showScheduleDialog;
                    setShowScheduleDialog(open);

                    // When dialog closes, force a refresh
                    if (wasOpen && !open) {
                        console.log("Dialog closing, refreshing data");
                        // Give time for the SyncSchedule component to complete any pending operations
                        setTimeout(() => {
                            refreshScheduleData();
                        }, 500);
                    }
                }}
            >
                <DialogContent className="max-w-3xl">
                    <DialogHeader>
                        <DialogTitle>Edit Sync Schedule</DialogTitle>
                    </DialogHeader>

                    <div className="py-4">
                        <SyncSchedule
                            value={scheduleConfig}
                            onChange={(newConfig) => {
                                console.log("Schedule config changed:", newConfig);
                                setScheduleConfig(newConfig);
                            }}
                            syncId={id}
                        />
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                console.log("Done button clicked");
                                setShowScheduleDialog(false);
                                // Simple and direct approach - reload the page when the dialog closes
                                setTimeout(() => window.location.reload(), 300);
                            }}
                        >
                            Done
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Job Details Dialog */}
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

export default SyncPlayground;
