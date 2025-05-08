import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Trash, Plus, Clock, Play } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import ReactFlow, {
    useNodesState,
    useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { SourceNode } from '@/components/sync/nodes/SourceNode';
import { TransformerNode } from '@/components/sync/nodes/TransformerNode';
import { DestinationNode } from '@/components/sync/nodes/DestinationNode';
import { EntityNode } from '@/components/sync/nodes/EntityNode';
import { Dag } from '@/components/sync/dag';
import {
    cleanEntityName,
    convertDagToFlowGraph
} from '@/new/dag/DagToFlow';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { SyncSchedule, SyncScheduleConfig } from '@/components/sync/SyncSchedule';
import { QueryTool } from '@/new/query/QueryTool';
import { LiveApiDoc } from '@/new/live-api-doc/LiveApiDoc';

// Register all node types
const nodeTypes = {
    sourceNode: SourceNode,
    transformerNode: TransformerNode,
    destinationNode: DestinationNode,
    entityNode: EntityNode
};

// Collection interface based on collection.py
interface Collection {
    name: string;
    readable_id: string;
    id: string;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    status?: string;
}

// Source Connection interface based on source_connection.py
interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    config_fields?: Record<string, any>;
    sync_id?: string;
    organization_id: string;
    created_at: string;
    modified_at: string;
    connection_id?: string;
    collection: string;
    created_by_email: string;
    modified_by_email: string;
    auth_fields?: Record<string, any> | string;
    status?: string;
    latest_sync_job_status?: string;
    latest_sync_job_id?: string;
    latest_sync_job_started_at?: string;
    latest_sync_job_completed_at?: string;
    cron_schedule?: string;
}

// Add SyncJob interface
interface SyncJob {
    id: string;
    sync_id: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
    started_at: string | null;
    completed_at: string | null;
    failed_at: string | null;
    entities_inserted: number;
    entities_updated: number;
    entities_deleted: number;
    entities_kept: number;
    entities_skipped: number;
    entities_encountered: Record<string, number>;
    error: string | null;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
}

const Collections = () => {
    const { readable_id } = useParams();
    const navigate = useNavigate();
    const [collection, setCollection] = useState<Collection | null>(null);
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isReloading, setIsReloading] = useState(false);
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLInputElement>(null);
    const { resolvedTheme } = useTheme();
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Add new state variables for sync job
    const [lastSyncJob, setLastSyncJob] = useState<SyncJob | null>(null);
    const [isLoadingSyncJob, setIsLoadingSyncJob] = useState(false);
    const [isRunningSyncJob, setIsRunningSyncJob] = useState(false);
    const [totalEntities, setTotalEntities] = useState<number>(0);
    const [totalRuntime, setTotalRuntime] = useState<number | null>(null);

    // Add ReactFlow state variables
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    const [entityDags, setEntityDags] = useState<Dag[]>([]);
    const [selectedDag, setSelectedDag] = useState<Dag | null>(null);
    const [entityDict, setEntityDict] = useState<Record<string, number>>({});
    const [selectedEntity, setSelectedEntity] = useState<string>('');

    // Add schedule related state variables
    const [showScheduleDialog, setShowScheduleDialog] = useState(false);
    const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
        type: "one-time",
        frequency: "custom"
    });
    const [nextRunTime, setNextRunTime] = useState<string | null>(null);

    // Effect to fit view when nodes or edges change
    useEffect(() => {
        if (reactFlowInstance) {
            reactFlowInstance.fitView({
                padding: 0.2,
                duration: 200
            });
        }
    }, [nodes, edges, reactFlowInstance]);

    // Move fetchCollection outside of useEffect
    const fetchCollection = async () => {
        if (!readable_id) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/collections/${readable_id}`);

            if (response.ok) {
                const data = await response.json();
                setCollection(data);
                // After successful collection fetch, fetch source connections
                fetchSourceConnections(data.readable_id);
            } else {
                if (response.status === 404) {
                    setError("Collection not found");
                } else {
                    const errorText = await response.text();
                    setError(`Failed to load collection: ${errorText}`);
                }
                setIsLoading(false);
            }
        } catch (err) {
            setError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
            setIsLoading(false);
        }
    };

    // Modify useEffect to use the function
    useEffect(() => {
        fetchCollection();
    }, [readable_id]);

    // Fetch source connections for this collection
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const data = await response.json();
                setSourceConnections(data);

                // Select first connection by default if there are any connections
                // and no connection is currently selected
                if (data.length > 0 && !selectedConnection) {
                    setSelectedConnection(data[0]);
                    await fetchSyncJobDetails(data[0]);
                }
            } else {
                console.error("Failed to load source connections:", await response.text());
                setSourceConnections([]);
            }
        } catch (err) {
            console.error("Error fetching source connections:", err);
            setSourceConnections([]);
        } finally {
            setIsLoading(false);
        }
    };

    // TODO: fetch source connection details, the above fetch gets listitem

    // Fetch sync job details using latest_sync_job_id or fetching the most recent job by sync_id
    const fetchSyncJobDetails = async (connection: SourceConnection) => {
        if (!connection.sync_id) {
            // Reset states if no sync ID available
            setLastSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
            return;
        }

        setIsLoadingSyncJob(true);
        try {
            let syncJobData: SyncJob;

            // If we have latest_sync_job_id, use it to fetch the specific job
            if (connection.latest_sync_job_id) {
                const response = await apiClient.get(`/sync/${connection.sync_id}/jobs/${connection.latest_sync_job_id}`);

                if (!response.ok) {
                    throw new Error("Failed to fetch sync job details");
                }

                syncJobData = await response.json();
            }
            // Otherwise, fetch all jobs for this sync and get the most recent one
            else {
                const jobsResponse = await apiClient.get(`/sync/${connection.sync_id}/jobs`);

                if (!jobsResponse.ok) {
                    throw new Error("Failed to fetch sync jobs");
                }

                const syncJobs: SyncJob[] = await jobsResponse.json();

                // Sort jobs by created_at date (newest first)
                const sortedJobs = syncJobs.sort((a, b) =>
                    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                );

                // If there are no jobs, return early
                if (sortedJobs.length === 0) {
                    setLastSyncJob(null);
                    setTotalEntities(0);
                    setTotalRuntime(null);
                    setIsLoadingSyncJob(false);
                    return;
                }

                // Use the most recent job
                syncJobData = sortedJobs[0];
            }

            setLastSyncJob(syncJobData);

            // Calculate total entities count
            const totalEntitiesCount =
                (syncJobData.entities_inserted || 0) +
                (syncJobData.entities_updated || 0) +
                (syncJobData.entities_kept || 0) +
                (syncJobData.entities_skipped || 0) -
                (syncJobData.entities_deleted || 0);
            setTotalEntities(totalEntitiesCount);

            // Calculate runtime for this job
            if (syncJobData.started_at && (syncJobData.completed_at || syncJobData.failed_at)) {
                const endTime = syncJobData.completed_at || syncJobData.failed_at;
                const runtime = new Date(endTime!).getTime() - new Date(syncJobData.started_at).getTime();
                setTotalRuntime(runtime);
            }

            // After we have the sync job data with entities_encountered, fetch entity DAGs
            if (syncJobData.sync_id && syncJobData.entities_encountered) {
                await fetchEntityDags(syncJobData.sync_id);
            }

        } catch (err) {
            console.error("Error fetching sync job details:", err);
            setLastSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
        } finally {
            setIsLoadingSyncJob(false);
        }
    };

    // Get the list of sync DAGs -> one per entity type
    const fetchEntityDags = async (syncId: string) => {
        try {
            const response = await apiClient.get(`/dag/sync/${syncId}/entity_dags`);

            if (!response.ok) {
                throw new Error('Failed to load entity DAGs');
            }

            const data = await response.json();
            setEntityDags(data);
            console.log('DAG data loaded:', data);
        } catch (error) {
            console.error('Error fetching entity DAGs:', error);
        }
    };

    // Add a function to process entities_encountered after DAGs are loaded
    const updateEntityDictionary = useCallback(() => {
        if (!lastSyncJob?.entities_encountered || !entityDags.length) {
            return; // Need both sync job and DAGs
        }

        console.log('Updating entity dictionary with DAGs and entities_encountered');

        // Get source name from entityDags
        const sourceName = entityDags[0].nodes
            .filter(node => node.type === 'source')
            .map(node => node.name)[0] || '';

        // Process the entities_encountered data with source name
        const cleanedDict = Object.entries(lastSyncJob.entities_encountered).reduce((acc, [key, value]) => {
            const cleanedName = cleanEntityName(key, sourceName);
            acc[cleanedName] = value;
            return acc;
        }, {} as Record<string, number>);

        console.log('Created cleaned entity dictionary:', cleanedDict, 'with source name:', sourceName);

        setEntityDict(cleanedDict);

        // If we have a new entity dict but no selected entity yet, select the first one
        if (Object.keys(cleanedDict).length > 0 && !selectedEntity) {
            setSelectedEntity(Object.keys(cleanedDict)[0]);
        }
    }, [lastSyncJob?.entities_encountered, entityDags, selectedEntity]);

    // Add useEffect to run updateEntityDictionary when dependencies change
    useEffect(() => {
        updateEntityDictionary();
    }, [updateEntityDictionary]);

    // Add useEffect to update the selected DAG when the selected entity changes
    useEffect(() => {
        if (!selectedEntity || entityDags.length === 0) {
            setSelectedDag(null);
            return;
        }

        // Find DAG that has name exactly matching the selected entity
        const exactMatch = entityDags.find(dag =>
            dag.name && dag.name.includes(selectedEntity + "Entity")
        );
        // Fall back to partial match if exact match not found
        const matchingDag = exactMatch || entityDags.find(dag =>
            dag.name && dag.name.includes(selectedEntity)
        );

        if (matchingDag) {
            setSelectedDag(matchingDag);
            console.log(`Selected DAG for entity "${selectedEntity}":`, matchingDag);
        } else {
            console.warn(`No DAG found for entity "${selectedEntity}"`);
            setSelectedDag(null);
        }
    }, [selectedEntity, entityDags]);

    // Add useEffect to update the flow graph when the selected DAG changes
    useEffect(() => {
        // First convert the DAG to basic flow graph
        convertDagToFlowGraph(selectedDag, setNodes, setEdges);
    }, [selectedDag, setNodes, setEdges]);

    // Run sync job using source-connection endpoint
    const handleRunSync = async () => {
        if (!selectedConnection?.id) {
            toast({
                title: "Error",
                description: "No source connection selected",
                variant: "destructive"
            });
            return;
        }

        try {
            setIsRunningSyncJob(true);
            const response = await apiClient.post(`/source-connections/${selectedConnection.id}/run`);

            if (!response.ok) {
                throw new Error("Failed to start sync job");
            }

            const newJob = await response.json();
            setLastSyncJob(newJob);

            toast({
                title: "Success",
                description: "Sync job started successfully"
            });

            // Refresh the connection data to update status
            setTimeout(() => refreshData(), 1000);
        } catch (error) {
            console.error("Error running sync:", error);
            toast({
                title: "Error",
                description: "Failed to start sync job",
                variant: "destructive"
            });
        } finally {
            setIsRunningSyncJob(false);
        }
    };

    // Format milliseconds to human-readable time
    const formatTotalRuntime = (ms: number) => {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    };

    // Format time since last run
    const formatTimeSince = (dateStr: string) => {
        const now = new Date();
        const date = new Date(dateStr);
        const diffMs = now.getTime() - date.getTime();
        const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
        const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

        if (diffHrs > 24) {
            const days = Math.floor(diffHrs / 24);
            return `${days}d ago`;
        } else if (diffHrs > 0) {
            return `${diffHrs}h ${diffMins}m ago`;
        } else {
            return `${diffMins}m ago`;
        }
    };

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        // Set input's initial value to current name
        if (nameInputRef.current) {
            nameInputRef.current.value = collection?.name || "";
        }
        setTimeout(() => nameInputRef.current?.focus(), 0);
    };

    const handleSaveNameChange = async () => {
        // Get value directly from input ref
        const newName = nameInputRef.current?.value || "";

        if (!newName.trim() || newName === collection?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/collections/${readable_id}`, { name: newName });
            if (!response.ok) throw new Error("Failed to update collection name");

            // Update local state after successful API call
            setCollection(prev => prev ? { ...prev, name: newName } : null);
            setIsEditingName(false);

            toast({
                title: "Success",
                description: "Collection name updated successfully"
            });
        } catch (error) {
            console.error("Error updating collection name:", error);
            toast({
                title: "Error",
                description: "Failed to update collection name",
                variant: "destructive"
            });
            setIsEditingName(false);
        }
    };

    // Enhanced refresh function
    const refreshData = async () => {
        if (!readable_id) return;

        setIsReloading(true);
        try {
            await fetchCollection();
            if (selectedConnection) {
                await fetchSyncJobDetails(selectedConnection);
            }
        } finally {
            setIsReloading(false);
        }
    };

    // Update selected connection and fetch sync job details
    const handleSelectConnection = async (connection: SourceConnection) => {
        setSelectedConnection(connection);
        await fetchSyncJobDetails(connection);
    };

    // Add this function to calculate the next run time based on cron
    const calculateNextRunTime = useCallback((cronExpression: string | null) => {
        if (!cronExpression) {
            return null;
        }

        try {
            // Parse the cron expression
            const parts = cronExpression.split(' ');
            if (parts.length !== 5) {
                console.error("Invalid cron expression format");
                return null;
            }

            const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

            // Get current date and create a copy for the next run
            const now = new Date();
            const nextRun = new Date(now);

            // Handle simple cases
            // If the expression is "0 0 * * *" (daily at midnight)
            if (minute === "0" && hour === "0" && dayOfMonth === "*" && month === "*") {
                // Set to next midnight
                nextRun.setDate(now.getDate() + 1);
                nextRun.setHours(0, 0, 0, 0);
            }
            // If the expression is "0 * * * *" (hourly)
            else if (minute === "0" && hour === "*") {
                // Set to the next hour
                nextRun.setHours(now.getHours() + 1, 0, 0, 0);
            }
            // If specific hour with any minute (0 5 * * *) - 5am daily
            else if (minute === "0" && !isNaN(parseInt(hour))) {
                const hourNum = parseInt(hour);
                // If today's occurrence has passed, move to tomorrow
                if (now.getHours() >= hourNum) {
                    nextRun.setDate(now.getDate() + 1);
                }
                nextRun.setHours(hourNum, 0, 0, 0);
            }
            // Default fallback for other patterns
            else {
                // For complex patterns, we'll just add a day as a fallback
                nextRun.setDate(now.getDate() + 1);
            }

            // Calculate time difference
            const diffMs = nextRun.getTime() - now.getTime();
            const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
            const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

            // Format the time difference
            if (diffHrs > 24) {
                const days = Math.floor(diffHrs / 24);
                return `${days} day${days > 1 ? 's' : ''}`;
            } else if (diffHrs > 0) {
                return `${diffHrs}h ${diffMins}m`;
            } else {
                return `${diffMins}m`;
            }
        } catch (error) {
            console.error("Error parsing cron expression:", error);
            return null;
        }
    }, []);

    // Add a function to refresh schedule data
    const refreshScheduleData = async () => {
        if (!selectedConnection?.sync_id) return;

        try {
            console.log("Starting schedule refresh");
            setIsReloading(true);

            // Make a targeted API call to get just the sync details
            const response = await apiClient.get(`/sync/${selectedConnection.sync_id}`);
            if (!response.ok) throw new Error("Failed to refresh sync data");

            const syncData = await response.json();
            console.log("Got sync data:", syncData);

            // Update the source connection state with the new schedule information
            setSelectedConnection(prev => {
                if (!prev) return null;
                console.log("Updating connection details with cron_schedule:", syncData.cron_schedule);
                return {
                    ...prev,
                    cron_schedule: syncData.cron_schedule,
                    modified_at: syncData.modified_at
                };
            });

            // Update the config state as well
            setScheduleConfig({
                type: syncData.cron_schedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: syncData.cron_schedule || undefined
            });

            // Update the next run time
            const nextRun = calculateNextRunTime(syncData.cron_schedule);
            setNextRunTime(nextRun);

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
            setIsReloading(false);
            console.log("Schedule refresh complete");
        }
    };

    // Update useEffect to initialize scheduleConfig and nextRunTime when selectedConnection changes
    useEffect(() => {
        if (selectedConnection?.sync_id) {
            // If the selected connection has sync_id, set up the schedule config
            setScheduleConfig({
                type: selectedConnection.cron_schedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: selectedConnection.cron_schedule || undefined
            });

            // Calculate next run time
            const nextRun = calculateNextRunTime(selectedConnection.cron_schedule || null);
            setNextRunTime(nextRun);
        }
    }, [selectedConnection, calculateNextRunTime]);

    if (error) {
        return (
            <div className="container mx-auto py-6">
                <h1 className="text-3xl font-bold mb-6">Collection Error</h1>
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <div className="font-medium">Error</div>
                    <div>{error}</div>
                </Alert>
                <div className="mt-4">
                    <Button onClick={() => navigate("/dashboard")}>
                        Return to Dashboard
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="container mx-auto py-6">
            {/* Header with Title and Status Badge */}
            <div className="flex items-center justify-between py-4">
                <div className="flex items-center gap-4">
                    {/* Source Icons */}
                    <div className="relative" style={{ width: "4rem", height: "2rem" }}>
                        {sourceConnections.map((connection, index) => (
                            <div
                                key={connection.id}
                                className="absolute w-12 h-12 rounded-md border border-black p-1 flex items-center justify-center overflow-hidden bg-background"
                                style={{
                                    bottom: `${index * 10}px`,
                                    right: `${index * 20}px`,
                                    zIndex: sourceConnections.length - index
                                }}
                            >
                                <img
                                    src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                    alt={connection.name}
                                    className="max-w-full max-h-full w-auto h-auto object-contain"
                                />
                            </div>
                        ))}
                    </div>

                    <div>
                        {isEditingName ? (
                            <div className="flex items-center gap-2">
                                <Input
                                    ref={nameInputRef}
                                    defaultValue={collection?.name || ""}
                                    className="text-xl font-bold h-9 min-w-[300px]"
                                    autoFocus
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            handleSaveNameChange();
                                        }
                                        if (e.key === 'Escape') {
                                            setIsEditingName(false);
                                        }
                                    }}
                                    onBlur={handleSaveNameChange}
                                />
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <h1 className="text-2xl font-bold tracking-tight">{collection?.name}</h1>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6"
                                    onClick={startEditingName}
                                >
                                    <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                {collection?.status && (
                                    <Badge className="rounded-full font-semibold">{collection.status.toUpperCase()}</Badge>
                                )}
                            </div>
                        )}
                        <p className="text-muted-foreground text-sm mt-1">
                            {collection?.readable_id}
                        </p>
                    </div>
                </div>
            </div>
            <div className="flex justify-end gap-2 mb-0">
                <Button
                    variant="outline"
                    onClick={refreshData}
                    disabled={isReloading}
                    className="gap-1 border-[2px] border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 hover:shadow-[inset_0_0_0_1px_#000000]"
                >
                    <RefreshCw className="h-4 w-4" />
                    {isReloading ? 'Reloading...' : 'Reload page'}
                </Button>
                <Button
                    variant="outline"
                    onClick={() => { }}
                    className="gap-1 border-[2px] border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 hover:shadow-[inset_0_0_0_1px_#000000]"
                >
                    <Plus className="h-4 w-4 border border-black" />
                    Add Source
                </Button>
                <Button
                    variant="outline"
                    onClick={() => { }}
                    className="gap-1 border-[2px] border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 hover:shadow-[inset_0_0_0_1px_#000000]"
                >
                    Refresh all sources
                </Button>
            </div>

            {/* Add QueryTool and LiveApiDoc when a connection with syncId is selected */}
            {selectedConnection?.sync_id && (
                <>
                    <div className='py-3 space-y-1 mt-0'>
                        <QueryTool syncId={selectedConnection.sync_id} />
                    </div>
                    <div className='py-0 space-y-1'>
                        <LiveApiDoc syncId={selectedConnection.sync_id} />
                    </div>
                </>
            )}

            <hr className="border-t border-gray-300 my-2 max-w-full" />

            {/* Source Connections Section */}
            <div className="mt-6">
                <h2 className="text-2xl font-bold tracking-tight mb-4">Source Connections</h2>

                <div className="flex flex-wrap gap-3">
                    {sourceConnections.map((connection) => (
                        <Button
                            key={connection.id}
                            variant="outline"
                            className={`w-60 h-13 flex items-center gap-2 justify-start overflow-hidden flex-shrink-0 flex-grow-0 border-[2px] ${selectedConnection?.id === connection.id
                                ? "border-black"
                                : "border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 hover:shadow-[inset_0_0_0_1px_#000000]"
                                }`}
                            onClick={() => handleSelectConnection(connection)}
                        >
                            <div className="w-10 h-10 rounded-md flex items-center justify-center overflow-hidden bg-background flex-shrink-0">
                                <img
                                    src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                    alt={connection.name}
                                    className="max-w-full max-h-full w-auto h-auto object-contain"
                                />
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className="text-[18px] font-medium truncate block text-left">{connection.name}</span>
                            </div>
                        </Button>
                    ))}
                </div>

                {sourceConnections.length === 0 && (
                    <div className="text-center py-6 text-muted-foreground">
                        No source connections found. Add a source connection to get started.
                    </div>
                )}
            </div>

            {/* Visualization Section */}
            {lastSyncJob && Object.keys(entityDict).length > 0 && (
                <div className="py-3 space-y-0 mt-10">
                    <div className="flex justify-between w-full mb-0 -mb-3">
                        <div className="flex gap-2 relative top-3">
                            {/* Entities count div */}
                            <div className="min-w-[120px] bg-gray-200 px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10">
                                {totalEntities > 0 ? `${totalEntities} total entities` : 'No entities yet'}
                            </div>

                            {/* Status div */}
                            {lastSyncJob && (
                                <div className="min-w-[120px] bg-gray-200 px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10">
                                    <div className="flex items-center">
                                        <span className={`inline-flex h-2.5 w-2.5 rounded-full mr-1.5
                                            ${lastSyncJob.status === 'completed' ? 'bg-green-500' :
                                                lastSyncJob.status === 'failed' ? 'bg-red-500' :
                                                    lastSyncJob.status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                                                        'bg-amber-500'}`}
                                        />
                                        <span className="capitalize">
                                            {lastSyncJob.status === 'in_progress' ? 'running' : lastSyncJob.status}
                                            {(lastSyncJob.status === 'in_progress' || lastSyncJob.status === 'pending') &&
                                                <span className="animate-pulse">...</span>
                                            }
                                        </span>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Last run info div */}
                        <div className="min-w-[150px] max-w-[35%] bg-white p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden">
                            {lastSyncJob ? (
                                <>
                                    <span className="whitespace-nowrap text-ellipsis overflow-hidden w-full text-right">
                                        Last run finished: {formatTimeSince(lastSyncJob.completed_at || lastSyncJob.failed_at || lastSyncJob.created_at)}
                                    </span>
                                    <span className="whitespace-nowrap text-ellipsis overflow-hidden w-full text-right">
                                        Total runtime: {totalRuntime ? formatTotalRuntime(totalRuntime) : 'N/A'}
                                    </span>
                                </>
                            ) : (
                                <span className="whitespace-nowrap text-ellipsis overflow-hidden w-full text-right">
                                    No sync jobs yet
                                </span>
                            )}
                        </div>
                    </div>
                    <Card className="overflow-hidden">
                        <CardHeader className="p-3">
                            {/* Button Tabs */}
                            <div className="flex flex-wrap gap-1">
                                {Object.keys(entityDict)
                                    .sort() // Sort keys alphabetically
                                    .map((key) => {
                                        // Determine if this button is selected
                                        const isSelected = key === selectedEntity;

                                        return (
                                            <Button
                                                key={key}
                                                variant={"outline"}
                                                className={`flex items-center gap-1 h-10 text-[15px] min-w-[90px] border-[2px] ${isSelected
                                                    ? "border-black"
                                                    : "border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 hover:shadow-[inset_0_0_0_1px_#000000]"
                                                    }`}
                                                onClick={() => setSelectedEntity(key)}
                                            >
                                                {key}
                                                <Badge
                                                    variant={isSelected ? "outline" : "default"}
                                                    className={"bg-black-50 text-black-700 border-black-200 pointer-events-none"}
                                                >
                                                    {entityDict[key]}
                                                </Badge>
                                            </Button>
                                        );
                                    })}
                            </div>
                        </CardHeader>
                        <CardContent className="p-1 pb-4">
                            <div className="h-[200px] -mt-4 w-full overflow-hidden">
                                <ReactFlow
                                    nodes={nodes}
                                    edges={edges}
                                    onNodesChange={onNodesChange}
                                    onEdgesChange={onEdgesChange}
                                    nodeTypes={nodeTypes}
                                    fitView
                                    fitViewOptions={{
                                        padding: 0.2,
                                        minZoom: 0.1,
                                        maxZoom: 1.5,
                                        duration: 200
                                    }}
                                    onInit={setReactFlowInstance}
                                    defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
                                    style={{
                                        touchAction: 'none',
                                        cursor: 'default'
                                    }}
                                    nodesDraggable={false}     // Disable node dragging
                                    nodesConnectable={false}   // Disable connecting nodes
                                    elementsSelectable={false} // Disable selection
                                    zoomOnScroll={false}       // Disable zoom on scroll
                                    panOnScroll={false}        // Disable panning
                                    panOnDrag={false}          // Disable panning when dragging
                                    zoomOnPinch={false}        // Disable pinch zoom
                                    zoomOnDoubleClick={false}  // Disable double-click zoom
                                    preventScrolling={true}    // Prevent scroll behavior
                                    proOptions={{ hideAttribution: true }}
                                />
                            </div>
                        </CardContent>
                    </Card>

                    <div className="flex justify-between mt-2 pt-1">
                        <div className="flex gap-2 flex-wrap pt-1">
                            <Button
                                key="sync-history"
                                variant="default"
                                className="flex items-center gap-1 h-10 text-[15px] min-w-[90px] border border-black shrink-0"
                                onClick={() => { }}
                            >
                                See sync history
                            </Button>
                            <Button
                                key="second-button"
                                variant="default"
                                className="flex items-center gap-1 h-10 text-[15px] min-w-[90px] border border-black shrink-0"
                                onClick={() => { }}
                            >
                                View details
                            </Button>
                        </div>

                        {/* Add the schedule information box */}
                        {selectedConnection?.sync_id && (
                            <div className="min-w-[150px] max-w-[35%] bg-white p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden pt-1">
                                <div className="flex items-center justify-end gap-2 w-full">
                                    <Clock className="w-4 h-4 text-black-500" />
                                    {selectedConnection.cron_schedule ? (
                                        <>
                                            <span className="whitespace-nowrap text-ellipsis overflow-hidden text-right">
                                                {nextRunTime ? `Sync due in ${nextRunTime}` : 'Scheduled'}
                                            </span>
                                        </>
                                    ) : (
                                        <span className="whitespace-nowrap text-ellipsis overflow-hidden text-right">
                                            No schedule set
                                        </span>
                                    )}
                                </div>
                                <span
                                    className="text-black-500 cursor-pointer hover:underline flex items-center justify-end gap-1 whitespace-nowrap"
                                    onClick={() => {
                                        setScheduleConfig({
                                            type: selectedConnection.cron_schedule ? "scheduled" : "one-time",
                                            frequency: "custom",
                                            cronExpression: selectedConnection.cron_schedule || undefined
                                        });
                                        setShowScheduleDialog(true);
                                    }}
                                >
                                    Change this
                                    <Pencil className="h-3 w-3" />
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Add Schedule Edit Dialog */}
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
                        {selectedConnection?.sync_id && (
                            <SyncSchedule
                                value={scheduleConfig}
                                onChange={(newConfig) => {
                                    console.log("Schedule config changed:", newConfig);
                                    setScheduleConfig(newConfig);
                                }}
                                syncId={selectedConnection.sync_id}
                            />
                        )}
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                console.log("Done button clicked");
                                setShowScheduleDialog(false);
                                // Simple and direct approach - reload the data when the dialog closes
                                setTimeout(() => refreshData(), 300);
                            }}
                        >
                            Done
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default Collections;
