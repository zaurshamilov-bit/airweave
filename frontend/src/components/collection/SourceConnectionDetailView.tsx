import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Play, Clock } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
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
} from '@/components/collection/DagToFlow';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { SyncSchedule, SyncScheduleConfig } from '@/components/sync/SyncSchedule';
import { QueryTool } from '@/components/collection/QueryTool';
import { LiveApiDoc } from '@/components/collection/LiveApiDoc';
import { useSyncSubscription } from "@/hooks/useSyncSubscription";
import { cn } from "@/lib/utils";

const nodeTypes = {
    sourceNode: SourceNode,
    transformerNode: TransformerNode,
    destinationNode: DestinationNode,
    entityNode: EntityNode
};

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

interface SourceConnectionJob {
    source_connection_id: string;
    id: string;
    sync_id?: string; // This may be needed for DAG fetching
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    created_at: string;
    modified_at: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
    entities_inserted: number;
    entities_updated: number;
    entities_deleted: number;
    entities_kept: number;
    entities_skipped: number;
    entities_encountered: Record<string, number>;
    started_at: string | null;
    completed_at: string | null;
    failed_at: string | null;
    error: string | null;
}

interface SourceConnectionDetailViewProps {
    sourceConnectionId: string;
}

const SourceConnectionDetailView = ({ sourceConnectionId }: SourceConnectionDetailViewProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    /********************************************
     * STATE DECLARATIONS - GROUPED BY PURPOSE
     ********************************************/

    // 1. Core connection and job state
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);
    const [lastSyncJob, setLastSyncJob] = useState<SourceConnectionJob | null>(null);
    const [isReloading, setIsReloading] = useState(false);
    const [isInitiatingSyncJob, setIsInitiatingSyncJob] = useState(false);
    const [finalPubSubData, setFinalPubSubData] = useState<{
        inserted: number;
        updated: number;
        deleted: number;
        kept: number;
        skipped: number;
        encountered: Record<string, number>;
    } | null>(null);

    // 2. Real-time updates state
    const [shouldForceSubscribe, setShouldForceSubscribe] = useState(false);

    // 3. Entity processing and visualization state
    const [totalEntities, setTotalEntities] = useState<number>(0);
    const [totalRuntime, setTotalRuntime] = useState<number | null>(null);
    const [entityDict, setEntityDict] = useState<Record<string, number>>({});
    const [selectedEntity, setSelectedEntity] = useState<string>('');
    const prevEntityDictRef = useRef<Record<string, number>>({});

    // 4. Graph visualization state
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    const [entityDags, setEntityDags] = useState<Dag[]>([]);
    const [selectedDag, setSelectedDag] = useState<Dag | null>(null);

    // 5. Scheduling state
    const [showScheduleDialog, setShowScheduleDialog] = useState(false);
    const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
        type: "one-time",
        frequency: "custom"
    });
    const [nextRunTime, setNextRunTime] = useState<string | null>(null);

    /********************************************
     * COMPUTED VALUES & DERIVED STATE
     ********************************************/

    // 1. Subscription control logic
    const shouldSubscribe = useMemo(() => {
        return shouldForceSubscribe ||
            (lastSyncJob?.status === 'pending' || lastSyncJob?.status === 'in_progress');
    }, [lastSyncJob?.status, shouldForceSubscribe]);

    // Subscribe to real-time updates when necessary
    const { updates, latestUpdate, isConnected: isPubSubConnected } = useSyncSubscription(
        shouldSubscribe ? lastSyncJob?.id || null : null
    );

    // 2. Status derived from most up-to-date source
    const status = useMemo(() => {
        // If we have real-time updates and are connected, use those first
        if (isPubSubConnected && latestUpdate) {
            if (latestUpdate.is_complete) return "completed";
            if (latestUpdate.is_failed) return "failed";
            return "in_progress";
        }
        // Otherwise fall back to the DB state
        return lastSyncJob?.status || "";
    }, [isPubSubConnected, latestUpdate, lastSyncJob?.status]);

    // 3. Active job status for conditional rendering
    const isSyncJobRunning = status === "in_progress" || status === "pending";

    // 4. Unified entity data from multiple sources
    const entityData = useMemo(() => {
        // If we have real-time updates and are connected, use those
        if (isPubSubConnected && latestUpdate && isSyncJobRunning) {
            return {
                inserted: latestUpdate.inserted || 0,
                updated: latestUpdate.updated || 0,
                deleted: latestUpdate.deleted || 0,
                kept: latestUpdate.kept || 0,
                skipped: latestUpdate.skipped || 0,
                encountered: latestUpdate.entities_encountered || {},
                isRealtimeData: true
            };
        }

        // If we have saved final PubSub data and the job just finished, use that
        if (finalPubSubData && (status === "completed" || status === "failed") && !isSyncJobRunning) {
            return {
                ...finalPubSubData,
                isRealtimeData: false
            };
        }

        // Otherwise use database state
        return {
            inserted: lastSyncJob?.entities_inserted || 0,
            updated: lastSyncJob?.entities_updated || 0,
            deleted: lastSyncJob?.entities_deleted || 0,
            kept: lastSyncJob?.entities_kept || 0,
            skipped: lastSyncJob?.entities_skipped || 0,
            encountered: lastSyncJob?.entities_encountered || {},
            isRealtimeData: false
        };
    }, [isPubSubConnected, latestUpdate, lastSyncJob, isSyncJobRunning, finalPubSubData, status]);

    // 5. Diagnostics for data source
    const isShowingRealtimeUpdates = shouldSubscribe && updates.length > 0 && isPubSubConnected;

    // 6. Display metrics for UI
    const total = entityData.inserted + entityData.updated + entityData.kept + entityData.deleted + entityData.skipped;

    /********************************************
     * API AND DATA FETCHING FUNCTIONS
     ********************************************/

    // 1. Main connection data fetching
    const fetchSourceConnectionDetails = async () => {
        try {
            const response = await apiClient.get(`/source-connections/${sourceConnectionId}`);

            if (response.ok) {
                const detailedData = await response.json();
                console.log("source connection details", detailedData);
                setSelectedConnection(detailedData);
                await fetchSourceConnectionJob(detailedData);
            } else {
                console.error("Failed to load source connection details:", await response.text());
            }
        } catch (err) {
            console.error("Error fetching source connection details:", err);
        }
    };

    // 2. Sync job data fetching
    const fetchSourceConnectionJob = async (connection: SourceConnection) => {
        if (!connection.sync_id || !connection.latest_sync_job_id) {
            // Reset states if no sync ID or job ID available
            setLastSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
            return;
        }

        try {
            const response = await apiClient.get(`/source-connections/${connection.id}/jobs/${connection.latest_sync_job_id}`);

            if (!response.ok) {
                console.error(`Failed to fetch job with ID ${connection.latest_sync_job_id}, status: ${response.status}`);
                setLastSyncJob(null);
                setTotalEntities(0);
                setTotalRuntime(null);
                return;
            }

            const sourceConnectionJob = await response.json();
            console.log("Source connection job:", sourceConnectionJob);
            setLastSyncJob(sourceConnectionJob);

            // Calculate runtime for this job
            if (sourceConnectionJob.started_at && (sourceConnectionJob.completed_at || sourceConnectionJob.failed_at)) {
                const endTime = sourceConnectionJob.completed_at || sourceConnectionJob.failed_at;
                const runtime = new Date(endTime!).getTime() - new Date(sourceConnectionJob.started_at).getTime();
                setTotalRuntime(runtime);
            }

            // After we have the job data with entities_encountered, fetch entity DAGs
            if (connection.sync_id && sourceConnectionJob.entities_encountered) {
                await fetchEntityDags(connection.sync_id);
            }
        } catch (err) {
            console.error("Error fetching source connection job:", err);
            setLastSyncJob(null);
            setTotalEntities(0);
            setTotalRuntime(null);
        }
    };

    // 3. Entity DAG fetching
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

    // 4. Schedule data refreshing
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

    // 5. General data reload
    const reloadData = async () => {
        setIsReloading(true);
        try {
            await fetchSourceConnectionDetails();
        } finally {
            setIsReloading(false);
        }
    };

    /********************************************
     * UI EVENT HANDLERS
     ********************************************/

    // 1. Run sync job
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
            setIsInitiatingSyncJob(true);
            const response = await apiClient.post(`/source-connections/${selectedConnection.id}/run`);

            if (!response.ok) {
                throw new Error("Failed to start sync job");
            }

            const newJob = await response.json();

            // Set the new job as current
            setLastSyncJob(newJob);

            // Force subscription for this new job
            setShouldForceSubscribe(true);
            // PubSub will handle updates - no need for manual reloading

        } catch (error) {
            console.error("Error running sync:", error);
            toast({
                title: "Error",
                description: "Failed to start sync job",
                variant: "destructive"
            });
        } finally {
            setIsInitiatingSyncJob(false);
        }
    };

    // 2. Schedule dialog handling
    const handleScheduleDialogClose = () => {
        setShowScheduleDialog(false);
        refreshScheduleData();
    };

    /********************************************
     * UTILITY FUNCTIONS
     ********************************************/

    // 1. Entity dictionary processing
    const updateEntityDictionary = useCallback(() => {
        // Use the unified entityData.encountered
        const entitiesEncountered = entityData.encountered;

        // Store current dictionary in ref
        if (Object.keys(entityDict).length > 0) {
            prevEntityDictRef.current = { ...entityDict };
        }

        // If we have no encountered entities but had them before,
        // don't empty the dictionary during state transitions
        if ((!entitiesEncountered || Object.keys(entitiesEncountered).length === 0) &&
            Object.keys(prevEntityDictRef.current).length > 0) {
            console.log('Preserving previous entity dictionary during transition');
            setEntityDict(prevEntityDictRef.current);
            return;
        }

        if (!entitiesEncountered || !entityDags.length) {
            return; // Need both entities and DAGs
        }

        // Get source name from entityDags
        const sourceName = entityDags[0].nodes
            .filter(node => node.type === 'source')
            .map(node => node.name)[0] || '';

        // Process the entities_encountered data with source name
        const cleanedDict = Object.entries(entitiesEncountered).reduce((acc, [key, value]) => {
            const cleanedName = cleanEntityName(key, sourceName);
            acc[cleanedName] = value as number;
            return acc;
        }, {} as Record<string, number>);

        console.log('Created cleaned entity dictionary:', cleanedDict, 'with source name:', sourceName);

        // Only update if we have actual entities
        if (Object.keys(cleanedDict).length > 0) {
            setEntityDict(cleanedDict);
        }

        // Select first entity if none selected
        if (Object.keys(cleanedDict).length > 0 && !selectedEntity) {
            setSelectedEntity(Object.keys(cleanedDict)[0]);
        }
    }, [entityData.encountered, entityDags, selectedEntity]);

    // 2. Schedule time calculation
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

    // 3. Time formatting utilities
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

    /********************************************
     * SIDE EFFECTS - ORDERED BY PRIORITY
     ********************************************/

    // 1. Initial data loading
    useEffect(() => {
        fetchSourceConnectionDetails();
    }, [sourceConnectionId]);

    // 2. PubSub subscription control
    useEffect(() => {
        if (latestUpdate?.is_complete || latestUpdate?.is_failed ||
            lastSyncJob?.status === 'completed' || lastSyncJob?.status === 'failed') {
            setShouldForceSubscribe(false);
        }
    }, [latestUpdate, lastSyncJob?.status]);

    // 3. PubSub completion handling
    useEffect(() => {
        if ((latestUpdate?.is_complete || latestUpdate?.is_failed) && lastSyncJob?.id) {
            // Save the final state from PubSub
            setFinalPubSubData({
                inserted: latestUpdate.inserted || 0,
                updated: latestUpdate.updated || 0,
                deleted: latestUpdate.deleted || 0,
                kept: latestUpdate.kept || 0,
                skipped: latestUpdate.skipped || 0,
                encountered: latestUpdate.entities_encountered || {},
            });

            // Mark the job as done in state
            setLastSyncJob(prev => prev ? {
                ...prev,
                status: latestUpdate.is_complete ? 'completed' : 'failed'
            } : prev);
        }
    }, [latestUpdate?.is_complete, latestUpdate?.is_failed]);

    // 4. Entity data processing
    useEffect(() => {
        const totalEntitiesCount =
            entityData.inserted +
            entityData.updated +
            entityData.kept +
            entityData.skipped -
            entityData.deleted;
        setTotalEntities(totalEntitiesCount);
    }, [entityData]);

    // 5. Entity dictionary maintenance
    useEffect(() => {
        updateEntityDictionary();
    }, [updateEntityDictionary]);

    // 6. Entity selection
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

    // 7. DAG visualization
    useEffect(() => {
        // Convert the DAG to basic flow graph
        convertDagToFlowGraph(selectedDag, setNodes, setEdges);
    }, [selectedDag, setNodes, setEdges]);

    // 8. ReactFlow visualization adjustments
    useEffect(() => {
        if (reactFlowInstance) {
            reactFlowInstance.fitView({
                padding: 0.2,
                duration: 200
            });
        }
    }, [nodes, edges, reactFlowInstance]);

    // 9. Schedule configuration
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

    // 10. Clean up on source change
    useEffect(() => {
        setFinalPubSubData(null);
    }, [sourceConnectionId]);

    // 11. Logging for diagnostic purposes
    useEffect(() => {
        if (updates.length > 0 && latestUpdate) {
            console.log(`[PubSub] Received update for job ${lastSyncJob?.id}:`, {
                isComplete: latestUpdate.is_complete,
                isFailed: latestUpdate.is_failed,
                counts: {
                    inserted: latestUpdate.inserted,
                    updated: latestUpdate.updated,
                    deleted: latestUpdate.deleted,
                    kept: latestUpdate.kept
                }
            });
        }
    }, [updates, latestUpdate, lastSyncJob?.id]);

    console.log(`[PubSub] Data source for job ${lastSyncJob?.id}: ${isShowingRealtimeUpdates ? 'LIVE UPDATES' : 'DATABASE'}`);

    /********************************************
     * RENDER
     ********************************************/

    if (!selectedConnection) {
        return (
            <div className="w-full py-6">
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <div className="font-medium">Error</div>
                    <div>Failed to load source connection details</div>
                </Alert>
            </div>
        );
    }

    return (
        <div className={cn(isDark ? "text-foreground" : "")}>
            {/* Visualization Section */}
            {lastSyncJob && (
                <div className="py-3 space-y-0 mt-10">
                    {/* Status Header */}
                    <div className="flex justify-between w-full mb-0 -mb-3">
                        <div className="flex gap-2 relative top-3">
                            {/* Entities count div */}
                            <div className={cn(
                                "min-w-[120px] px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10",
                                isDark ? "bg-gray-800" : "bg-gray-200"
                            )}>
                                {totalEntities > 0 ? `${totalEntities} total entities` : 'No entities yet'}
                            </div>

                            {/* Status div */}
                            <div className={cn(
                                "min-w-[120px] px-3 py-2 rounded-md shadow-sm text-center text-[15px] flex items-center justify-center overflow-hidden whitespace-nowrap text-ellipsis h-10",
                                isDark ? "bg-gray-800" : "bg-gray-200"
                            )}>
                                <div className="flex items-center">
                                    <span className={`inline-flex h-2.5 w-2.5 rounded-full mr-1.5
                                        ${status === 'completed' ? 'bg-green-500' :
                                            status === 'failed' ? 'bg-red-500' :
                                                status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                                                    'bg-amber-500'}`}
                                    />
                                    <span className="capitalize">
                                        {status === 'in_progress' ? 'running' : status}
                                        {(status === 'in_progress' || status === 'pending') &&
                                            <span className="animate-pulse">...</span>
                                        }
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Last run info div */}
                        <div className={cn(
                            "min-w-[150px] max-w-[35%] p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden",
                            isDark ? "bg-gray-800" : "bg-white"
                        )}>
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

                    {/* Entity Visualization */}
                    <Card className={cn(
                        "overflow-hidden",
                        isDark ? "border-gray-700 bg-gray-800/30" : ""
                    )}>
                        <CardHeader className="p-3">
                            {/* Entity Selection Buttons */}
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
                                                className={cn(
                                                    "flex items-center gap-1 h-10 text-[15px] min-w-[90px]",
                                                    isSelected
                                                        ? "border-[2px] border-black dark:border-white"
                                                        : "border-transparent shadow-[inset_0_0_0_1px_#d1d5db] hover:bg-gray-100 dark:shadow-[inset_0_0_0_1px_#4b5563] dark:hover:bg-gray-800"
                                                )}
                                                onClick={() => setSelectedEntity(key)}
                                            >
                                                {key}
                                                <Badge
                                                    variant={isSelected ? "outline" : "default"}
                                                    className={cn(
                                                        "pointer-events-none",
                                                        isDark ? "bg-gray-700 text-gray-200 border-gray-600" : "bg-black-50 text-black-700 border-black-200"
                                                    )}
                                                >
                                                    {entityDict[key]}
                                                </Badge>
                                            </Button>
                                        );
                                    })}
                            </div>
                        </CardHeader>
                        <CardContent className="p-1 pb-4">
                            {/* Flow Diagram */}
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
                                    nodesDraggable={false}
                                    nodesConnectable={false}
                                    elementsSelectable={false}
                                    zoomOnScroll={false}
                                    panOnScroll={false}
                                    panOnDrag={false}
                                    zoomOnPinch={false}
                                    zoomOnDoubleClick={false}
                                    preventScrolling={true}
                                    proOptions={{ hideAttribution: true }}
                                />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Action Buttons */}
                    <div className="flex justify-between mt-2 pt-1">
                        <div className="flex gap-2 flex-wrap pt-1">
                            <Button
                                key="sync-history"
                                variant="default"
                                className={cn(
                                    "flex items-center gap-1 h-10 text-[15px] min-w-[90px] border shrink-0",
                                    isDark ? "border-gray-600" : "border-black"
                                )}
                                onClick={() => { }}
                            >
                                See sync history
                            </Button>
                            <Button
                                key="second-button"
                                variant="default"
                                className={cn(
                                    "flex items-center gap-1 h-10 text-[15px] min-w-[90px] border shrink-0",
                                    isDark ? "border-gray-600" : "border-black"
                                )}
                                onClick={() => { }}
                            >
                                View details
                            </Button>
                            <Button
                                key="run-sync"
                                variant="default"
                                className={cn(
                                    "flex items-center gap-1 h-10 text-[15px] min-w-[90px] border shrink-0",
                                    isDark ? "border-gray-600" : "border-black"
                                )}
                                onClick={handleRunSync}
                                disabled={isInitiatingSyncJob || isSyncJobRunning}
                            >
                                {isInitiatingSyncJob ? 'Starting...' : 'Run sync'}
                                <Play className="h-4 w-4 ml-1" />
                            </Button>
                        </div>

                        {/* Schedule information box */}
                        {selectedConnection?.sync_id && (
                            <div className={cn(
                                "min-w-[150px] max-w-[35%] p-3 rounded-md shadow-sm flex flex-col text-[13px] items-end justify-center overflow-hidden pt-1",
                                isDark ? "bg-gray-800" : "bg-white"
                            )}>
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
                                    className={cn(
                                        "cursor-pointer hover:underline flex items-center justify-end gap-1 whitespace-nowrap",
                                        isDark ? "text-gray-400" : "text-black-500"
                                    )}
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

            {/* Schedule Edit Dialog */}
            <Dialog
                open={showScheduleDialog}
                onOpenChange={(open) => {
                    setShowScheduleDialog(open);
                    if (!open) {
                        // Only refresh when dialog closes
                        refreshScheduleData();
                    }
                }}
            >
                <DialogContent className={cn(
                    "max-w-3xl",
                    isDark ? "bg-card-solid border-border" : ""
                )}>
                    <DialogHeader>
                        <DialogTitle className={isDark ? "text-foreground" : ""}>Edit Sync Schedule</DialogTitle>
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
                            className={isDark ? "bg-gray-800 text-white hover:bg-gray-700" : ""}
                            onClick={handleScheduleDialogClose}
                        >
                            Done
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Sync Progress */}
            {lastSyncJob && (
                <div className="w-full my-6">
                    <Card className={cn(
                        "w-full max-w-none shadow-sm relative overflow-hidden",
                        isSyncJobRunning ? 'live-pulsing-bg' : '',
                        isDark ? "border-gray-700 bg-gray-800/30" : ""
                    )}>
                        <CardContent className="space-y-4 relative z-10 mt-4">
                            {/* Normalized multi-segment progress bar */}
                            <div className={cn(
                                "relative w-full h-3 rounded-md overflow-hidden",
                                isDark ? "bg-gray-700/50" : "bg-secondary/20"
                            )}>
                                <div
                                    className="absolute left-0 top-0 h-3 bg-green-500"
                                    style={{ width: `${total > 0 ? (entityData.inserted / total) * 100 : 0}%` }}
                                />
                                <div
                                    className="absolute top-0 h-3 bg-cyan-500"
                                    style={{
                                        left: `${total > 0 ? (entityData.inserted / total) * 100 : 0}%`,
                                        width: `${total > 0 ? (entityData.updated / total) * 100 : 0}%`
                                    }}
                                />
                                <div
                                    className="absolute top-0 h-3 bg-primary"
                                    style={{
                                        left: `${total > 0 ? ((entityData.inserted + entityData.updated) / total) * 100 : 0}%`,
                                        width: `${total > 0 ? (entityData.kept / total) * 100 : 0}%`
                                    }}
                                />
                                <div
                                    className="absolute top-0 h-3 bg-red-500"
                                    style={{
                                        left: `${total > 0 ? ((entityData.inserted + entityData.updated + entityData.kept) / total) * 100 : 0}%`,
                                        width: `${total > 0 ? (entityData.deleted / total) * 100 : 0}%`
                                    }}
                                />
                                <div
                                    className="absolute top-0 h-3 bg-yellow-500"
                                    style={{
                                        left: `${total > 0 ? ((entityData.inserted + entityData.updated + entityData.kept + entityData.deleted) / total) * 100 : 0}%`,
                                        width: `${total > 0 ? (entityData.skipped / total) * 100 : 0}%`
                                    }}
                                />
                            </div>

                            {/* Legend */}
                            <div className="text-xs mt-2 flex items-center justify-between flex-wrap gap-2">
                                <div className="flex items-center space-x-1">
                                    <span className="w-3 h-3 block bg-green-500 rounded-full" />
                                    <span>Inserted</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className="w-3 h-3 block bg-cyan-500 rounded-full" />
                                    <span>Updated</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className="w-3 h-3 block bg-primary rounded-full" />
                                    <span>Kept</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className="w-3 h-3 block bg-red-500 rounded-full" />
                                    <span>Deleted</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className="w-3 h-3 block bg-yellow-500 rounded-full" />
                                    <span>Skipped</span>
                                </div>
                            </div>

                            {/* Tally so far */}
                            <div className="space-y-2 text-sm mt-4">
                                <div className="flex justify-between">
                                    <span>Inserted</span>
                                    <span>{entityData.inserted.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Updated</span>
                                    <span>{entityData.updated.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Kept</span>
                                    <span>{entityData.kept.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Deleted</span>
                                    <span>{entityData.deleted.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Skipped</span>
                                    <span>{entityData.skipped.toLocaleString()}</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
};

export default SourceConnectionDetailView;
