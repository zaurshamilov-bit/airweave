import { useState, useCallback, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import ReactFlow, {
    useNodesState,
    useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './Playground.css';
import { SourceNode } from '@/components/sync/nodes/SourceNode';
import { TransformerNode } from '@/components/sync/nodes/TransformerNode';
import { DestinationNode } from '@/components/sync/nodes/DestinationNode';
import { EntityNode } from '@/components/sync/nodes/EntityNode';
import { apiClient } from '@/lib/api';
import { Dag } from '@/components/sync/dag';
import { QueryTool } from '@/new/query/QueryTool';
import { LiveApiDoc } from '@/new/live-api-doc/LiveApiDoc';
import SyncPlayground from '@/new/SyncPlayground';
import { format } from 'date-fns';
import { RefreshCw, Play, Trash, Pencil, Clock } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import {
    cleanEntityName,
    convertDagToFlowGraph
} from '@/new/dag/DagToFlow';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { SyncSchedule, SyncScheduleConfig } from '@/components/sync/SyncSchedule';

// TODO: this should be got from api call
const SYNC_ID = '1e02d9fb-bfb4-49e2-9472-a40cb4f5fad6';

// Register all node types
const nodeTypes = {
    sourceNode: SourceNode,
    transformerNode: TransformerNode,
    destinationNode: DestinationNode,
    entityNode: EntityNode
};

// Define interfaces for API responses
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
    status?: string;
}

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

const Playground = () => {
    // Replace the dummyData state with actual data from entityDict
    const [entityDags, setEntityDags] = useState<Dag[]>([]);
    const [selectedDag, setSelectedDag] = useState<Dag | null>(null);
    const [entityDict, setEntityDict] = useState<Record<string, number>>({});
    const [selectedEntity, setSelectedEntity] = useState<string>('');

    // Add new state variables for sync details and jobs
    const [syncDetails, setSyncDetails] = useState<SyncDetails | null>(null);
    const [lastSync, setLastSync] = useState<SyncJob | null>(null);
    const [isRunningSync, setIsRunningSync] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [totalRuntime, setTotalRuntime] = useState<number | null>(null);
    const [totalEntities, setTotalEntities] = useState<number>(0);
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);

    // Name editing state
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLInputElement>(null);

    // Set up the ReactFlow state
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);

    // Add these state variables with the existing state variables at the top
    const [showScheduleDialog, setShowScheduleDialog] = useState(false);
    const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
        type: "one-time",
        frequency: "custom"
    });

    // Add with existing state variables
    const [nextRunTime, setNextRunTime] = useState<string | null>(null);

    // Add effect to fit view when nodes or edges change
    useEffect(() => {
        if (reactFlowInstance) {
            reactFlowInstance.fitView({
                padding: 0.2,
                duration: 200
            });
        }
    }, [nodes, edges, reactFlowInstance]);

    // Fetch sync details
    const fetchSyncDetails = async () => {
        try {
            // Fetch sync details
            const syncResponse = await apiClient.get(`/sync/${SYNC_ID}`);

            if (!syncResponse.ok) {
                throw new Error("Failed to fetch sync details");
            }

            const syncData: SyncDetails = await syncResponse.json();
            syncData.status = "TODO"; // Setting default status
            setSyncDetails(syncData);

            console.log('Sync details loaded:', syncData);
        } catch (error) {
            console.error("Error fetching sync details:", error);
        }
    };

    // Fetch last sync job
    const fetchLastSyncJob = async () => {
        try {
            // Fetch all sync jobs for this sync
            const jobsResponse = await apiClient.get(`/sync/${SYNC_ID}/jobs`);

            if (!jobsResponse.ok) {
                throw new Error("Failed to fetch sync jobs");
            }

            const syncJobs: SyncJob[] = await jobsResponse.json();

            // Sort jobs by created_at date (newest first)
            const sortedJobs = syncJobs.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );

            // Set the most recent job as the last sync
            if (sortedJobs.length > 0) {
                const latestJob = sortedJobs[0];
                setLastSync(latestJob);

                // Calculate total entities count
                const totalEntitiesCount =
                    (latestJob.entities_inserted || 0) +
                    (latestJob.entities_updated || 0) +
                    (latestJob.entities_kept || 0) +
                    (latestJob.entities_skipped || 0) -
                    (latestJob.entities_deleted || 0);
                setTotalEntities(totalEntitiesCount);

                // Calculate total runtime across all completed jobs
                let totalTime = 0;
                syncJobs.forEach(job => {
                    const endTime = job.completed_at || job.failed_at;
                    if (job.started_at && endTime) {
                        totalTime += new Date(endTime).getTime() - new Date(job.started_at).getTime();
                    }
                });
                setTotalRuntime(totalTime);
            }

            console.log('Sync jobs loaded:', syncJobs);
        } catch (error) {
            console.error("Error fetching last sync job:", error);
        }
    };

    // Add a new function to process entities_encountered after DAGs are loaded
    const updateEntityDictionary = useCallback(() => {
        if (!lastSync?.entities_encountered || !entityDags.length) {
            return; // Need both sync job and DAGs
        }

        console.log('Updating entity dictionary with DAGs and entities_encountered');

        // Get source name from entityDags
        const sourceName = entityDags[0].nodes
            .filter(node => node.type === 'source')
            .map(node => node.name)[0] || '';

        // Process the entities_encountered data with source name
        const cleanedDict = Object.entries(lastSync.entities_encountered).reduce((acc, [key, value]) => {
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
    }, [lastSync?.entities_encountered, entityDags, selectedEntity]);

    // Add useEffect to run updateEntityDictionary when dependencies change
    useEffect(() => {
        updateEntityDictionary();
    }, [updateEntityDictionary]);

    // Change the refresh order
    const refreshData = async () => {
        setIsRefreshing(true);
        try {
            await fetchSyncDetails();
            // First fetch DAGs, then fetch jobs
            await fetchEntityDags();
            await fetchLastSyncJob();
        } finally {
            setIsRefreshing(false);
        }
    };

    // Modify initial data fetch order
    useEffect(() => {
        const loadData = async () => {
            await fetchSyncDetails();
            await fetchEntityDags(); // Fetch DAGs first
            await fetchLastSyncJob(); // Then fetch jobs
        };

        loadData();
    }, []);

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        // Set input's initial value to current name
        if (nameInputRef.current) {
            nameInputRef.current.value = syncDetails?.name || "";
        }
        setTimeout(() => nameInputRef.current?.focus(), 0);
    };

    const handleSaveNameChange = async () => {
        // Get value directly from input ref
        const newName = nameInputRef.current?.value || "";

        if (!newName.trim() || newName === syncDetails?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/sync/${SYNC_ID}`, { name: newName });
            if (!response.ok) throw new Error("Failed to update sync name");

            // Update local state after successful API call
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

    // Get the list of sync DAGs -> one per entity type
    const fetchEntityDags = async () => {
        try {
            const response = await apiClient.get(`/dag/sync/${SYNC_ID}/entity_dags`);

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

    // Run sync
    const handleRunSync = async () => {
        try {
            setIsRunningSync(true);
            const response = await apiClient.post(`/sync/${SYNC_ID}/run`);

            if (!response.ok) {
                throw new Error("Failed to start sync job");
            }

            const newJob = await response.json();
            setLastSync(newJob);

            toast({
                title: "Success",
                description: "Sync job started successfully"
            });

            console.log('Sync job started:', newJob);
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

    // Handle delete
    const handleDelete = async () => {
        try {
            const response = await apiClient.delete(`/sync/${SYNC_ID}`);
            if (!response.ok) throw new Error("Failed to delete sync");

            toast({
                title: "Success",
                description: "Synchronization deleted successfully"
            });
            // Redirect logic would go here if needed
        } catch (error) {
            console.error("Error deleting sync:", error);
            toast({
                title: "Error",
                description: "Failed to delete synchronization",
                variant: "destructive"
            });
        } finally {
            setShowDeleteDialog(false);
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

    // Add this useEffect to update the selected DAG when the selected entity changes
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
    }, [selectedEntity, entityDags, setNodes, setEdges]);

    // Add this useEffect to update the flow graph when the selected DAG changes
    useEffect(() => {
        // First convert the DAG to basic flow graph
        convertDagToFlowGraph(selectedDag, setNodes, setEdges);
    }, [selectedDag, setNodes, setEdges]);

    // Add this function to refresh schedule data
    const refreshScheduleData = async () => {
        if (!SYNC_ID) return;

        try {
            console.log("Starting schedule refresh");
            // Show loading indicator
            setIsRefreshing(true);

            // Make a targeted API call to get just the sync details
            const response = await apiClient.get(`/sync/${SYNC_ID}`);
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
                    modified_at: syncData.modified_at
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

    // Update useEffect to initialize scheduleConfig when syncDetails is loaded
    useEffect(() => {
        // Set the initial schedule config when syncDetails is loaded
        if (syncDetails) {
            setScheduleConfig({
                type: syncDetails.cron_schedule ? "scheduled" : "one-time",
                frequency: "custom",
                cronExpression: syncDetails.cron_schedule || undefined
            });
        }
    }, [syncDetails]);

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

            // Handle simple cases - for a complete solution you'd need to handle
            // all cron syntax including */5, ranges like 1-5, lists like 1,3,5, etc.

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

    // Add this useEffect to update nextRunTime when syncDetails changes
    useEffect(() => {
        const nextRun = calculateNextRunTime(syncDetails?.cron_schedule || null);
        setNextRunTime(nextRun);
    }, [syncDetails?.cron_schedule, calculateNextRunTime]);

    return (
        <div>
            {/* Header with Title and Status Badge */}
            <div className="flex items-center justify-between container py-4">
                <div className="flex items-center gap-4">
                    <div>
                        {isEditingName ? (
                            <div className="flex items-center gap-2">
                                <Input
                                    ref={nameInputRef}
                                    // Use uncontrolled input to prevent re-renders during typing
                                    defaultValue={syncDetails?.name || ""}
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
                                <h1 className="text-2xl font-bold tracking-tight">{syncDetails?.name}</h1>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6"
                                    onClick={startEditingName}
                                >
                                    <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                <Badge className="rounded-full font-semibold">{syncDetails?.status?.toUpperCase()}</Badge>
                            </div>
                        )}
                        <p className="text-muted-foreground text-sm mt-1">
                            TODO: respectable-sparrow.airweave.ai
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        onClick={refreshData}
                        disabled={isRefreshing}
                        className="gap-1"
                    >
                        <RefreshCw className="h-4 w-4" />
                        {isRefreshing ? 'Refreshing...' : 'Refresh'}
                    </Button>
                    <Button
                        variant="default"
                        onClick={handleRunSync}
                        disabled={isRunningSync || lastSync?.status === 'in_progress' || lastSync?.status === 'pending'}
                    >
                        <Play className="mr-2 h-4 w-4" />
                        {isRunningSync ? 'Starting...' : 'Run Sync'}
                    </Button>
                    <Button
                        variant="outline"
                        onClick={() => setShowDeleteDialog(true)}
                        className="text-destructive hover:bg-destructive/10"
                    >
                        <Trash className="mr-2 h-4 w-4" />
                        Delete
                    </Button>
                </div>
            </div>

            <div className='container py-3 space-y-1'>
                <QueryTool syncId={SYNC_ID} />
            </div>
            <div className='container py-0 space-y-1'>
                <LiveApiDoc syncId={SYNC_ID} />
            </div>

            <hr className="container mx-auto border-t border-gray-300 my-2 max-w-[calc(100%-3rem)]" />

            <div className="container py-3 space-y-0 mt-10">
                <div className="flex justify-between w-full mb-0 -mb-3">
                    <div className="flex gap-2 relative top-3">
                        {/* Entities count div */}
                        <div className="min-w-[120px] bg-gray-200 px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10">
                            {totalEntities > 0 ? `${totalEntities} total entities` : 'No entities yet'}
                        </div>

                        {/* Status div */}
                        {lastSync && (
                            <div className="min-w-[120px] bg-gray-200 px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10">
                                <div className="flex items-center">
                                    <span className={`inline-flex h-2.5 w-2.5 rounded-full mr-1.5
                                        ${lastSync.status === 'completed' ? 'bg-green-500' :
                                            lastSync.status === 'failed' ? 'bg-red-500' :
                                                lastSync.status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                                                    'bg-amber-500'}`}
                                    />
                                    <span className="capitalize">
                                        {lastSync.status === 'in_progress' ? 'running' : lastSync.status}
                                        {(lastSync.status === 'in_progress' || lastSync.status === 'pending') &&
                                            <span className="animate-pulse">...</span>
                                        }
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Last run info div */}
                    <div className="min-w-[150px] max-w-[35%] bg-white p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden">
                        {lastSync ? (
                            <>
                                <span className="whitespace-nowrap text-ellipsis overflow-hidden w-full text-right">
                                    Last run finished: {formatTimeSince(lastSync.completed_at || lastSync.failed_at || lastSync.created_at)}
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
                    <div className="min-w-[150px] max-w-[35%] bg-white p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden pt-1">
                        <div className="flex items-center justify-end gap-2 w-full">
                            <Clock className="w-4 h-4 text-black-500" />
                            {syncDetails?.cron_schedule ? (
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
                                    type: syncDetails?.cron_schedule ? "scheduled" : "one-time",
                                    frequency: "custom",
                                    cronExpression: syncDetails?.cron_schedule || undefined
                                });
                                setShowScheduleDialog(true);
                            }}
                        >
                            Change this
                            <Pencil className="h-3 w-3" />
                        </span>
                    </div>
                </div>
            </div>

            <div className="mt-8">
                <SyncPlayground id={SYNC_ID} />
            </div>

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
                        <SyncSchedule
                            value={scheduleConfig}
                            onChange={(newConfig) => {
                                console.log("Schedule config changed:", newConfig);
                                setScheduleConfig(newConfig);
                            }}
                            syncId={SYNC_ID}
                        />
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

export default Playground;
