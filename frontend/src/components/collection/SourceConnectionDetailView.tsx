import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, RefreshCw, Pencil, Play, Clock, Loader2 } from "lucide-react";
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
    shouldForceSubscribe?: boolean;
    onSubscriptionComplete?: () => void;
}

const SourceConnectionDetailView = ({
    sourceConnectionId,
    shouldForceSubscribe = false,
    onSubscriptionComplete
}: SourceConnectionDetailViewProps) => {
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
    const [internalShouldForceSubscribe, setInternalShouldForceSubscribe] = useState(false);

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

    // Add this near other useRef declarations:
    const flowContainerRef = useRef<HTMLDivElement>(null);

    /********************************************
     * COMPUTED VALUES & DERIVED STATE
     ********************************************/

    // 1. Subscription control logic
    const shouldSubscribe = useMemo(() => {
        return shouldForceSubscribe || internalShouldForceSubscribe ||
            (lastSyncJob?.status === 'pending' || lastSyncJob?.status === 'in_progress');
    }, [lastSyncJob?.status, internalShouldForceSubscribe, shouldForceSubscribe]);

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

    // Add this to prevent entity dictionary from completely emptying during transitions
    // This preserves the previous entity dictionary if new data doesn't have entities yet
    const stableEntityDict = useMemo(() => {
        if (Object.keys(entityDict).length > 0) {
            return entityDict;
        }
        return prevEntityDictRef.current;
    }, [entityDict]);

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
            setInternalShouldForceSubscribe(true);
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
            setInternalShouldForceSubscribe(false);

            // Call the completion callback if provided
            if (onSubscriptionComplete) {
                onSubscriptionComplete();
            }
        }
    }, [latestUpdate, lastSyncJob?.status, onSubscriptionComplete]);

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
                duration: 0
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

    // Add this effect to handle resizing
    useEffect(() => {
        if (!reactFlowInstance || !flowContainerRef.current) return;

        const resizeObserver = new ResizeObserver(() => {
            setTimeout(() => {
                reactFlowInstance.fitView({
                    padding: 0.2,
                    duration: 0
                });
            }, 0);
        });

        resizeObserver.observe(flowContainerRef.current);

        return () => {
            if (flowContainerRef.current) {
                resizeObserver.unobserve(flowContainerRef.current);
            }
        };
    }, [reactFlowInstance]);

    // Modify the Reset ReactFlow instance when connection changes
    useEffect(() => {
        // Clear the graph when connection changes
        setNodes([]);
        setEdges([]);
        setSelectedEntity('');
        setEntityDict({});
        setSelectedDag(null);
        setEntityDags([]); // Reset entity DAGs too

        // If we have a ReactFlow instance, force a complete reset
        if (reactFlowInstance) {
            reactFlowInstance.setNodes([]);
            reactFlowInstance.setEdges([]);

            // Force a reset of the instance after a delay
            setTimeout(() => {
                reactFlowInstance.fitView({ padding: 0.2 });
            }, 100);
        }
    }, [sourceConnectionId, reactFlowInstance]);

    console.log(`[PubSub] Data source for job ${lastSyncJob?.id}: ${isShowingRealtimeUpdates ? 'LIVE UPDATES' : 'DATABASE'}`);

    /********************************************
     * RENDER
     ********************************************/

    if (!selectedConnection) {
        return (
            <div className="w-full py-6">
                <div className="flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2">Loading connection details...</span>
                </div>
            </div>
        );
    }

    return (
        <div className={cn(isDark ? "text-foreground" : "")}>
            {/* Visualization Section */}
            {lastSyncJob && (
                <div className="py-2 space-y-3 mt-4">
                    {/* Status Dashboard */}
                    <div className="grid grid-cols-12 gap-3">
                        {/* Status Stats Cards - Add stable min-height to prevent layout shifts */}
                        <div className="col-span-12 md:col-span-8 grid grid-cols-3 gap-3">
                            {/* Entities Card */}
                            <div className={cn(
                                "col-span-1 rounded-lg p-3 flex flex-col shadow-sm transition-all duration-200 min-h-[5.5rem]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-xs uppercase tracking-wider mb-1 font-medium opacity-60">
                                    Entities
                                </div>
                                <div className="text-2xl font-semibold">
                                    {totalEntities.toLocaleString()}
                                </div>
                            </div>

                            {/* Status Card */}
                            <div className={cn(
                                "col-span-1 rounded-lg p-3 flex flex-col shadow-sm transition-all duration-200 min-h-[5.5rem]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-xs uppercase tracking-wider mb-1 font-medium opacity-60">
                                    Status
                                </div>
                                <div className="text-lg font-medium flex items-center">
                                    <span className={`inline-flex h-3 w-3 rounded-full mr-2
                                        ${status === 'completed' ? 'bg-green-500' :
                                            status === 'failed' ? 'bg-red-500' :
                                                status === 'in_progress' ? 'bg-blue-500 animate-pulse' :
                                                    'bg-amber-500'}`}
                                    />
                                    <span className="capitalize">
                                        {status === 'in_progress' ? 'Running' : status}
                                        {(status === 'in_progress' || status === 'pending') &&
                                            <span className="animate-pulse ml-1">•••</span>
                                        }
                                    </span>
                                </div>
                            </div>

                            {/* Runtime Card */}
                            <div className={cn(
                                "col-span-1 rounded-lg p-3 flex flex-col shadow-sm transition-all duration-200 min-h-[5.5rem]",
                                isDark
                                    ? "bg-gray-800/60 border border-gray-700/50"
                                    : "bg-white border border-gray-100"
                            )}>
                                <div className="text-xs uppercase tracking-wider mb-1 font-medium opacity-60">
                                    Runtime
                                </div>
                                <div className="text-lg font-medium">
                                    {totalRuntime ? formatTotalRuntime(totalRuntime) : 'N/A'}
                                </div>
                            </div>
                        </div>

                        {/* Schedule Card */}
                        <div className={cn(
                            "col-span-12 md:col-span-4 rounded-lg p-3 flex flex-col justify-between shadow-sm transition-all duration-200 min-h-[5.5rem]",
                            isDark
                                ? "bg-gray-800/60 border border-gray-700/50"
                                : "bg-white border border-gray-100"
                        )}>
                            <div className="flex items-center justify-between mb-1">
                                <div className="text-xs uppercase tracking-wider font-medium opacity-60">
                                    Schedule
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-1 px-1 rounded-md"
                                    onClick={() => {
                                        setScheduleConfig({
                                            type: selectedConnection.cron_schedule ? "scheduled" : "one-time",
                                            frequency: "custom",
                                            cronExpression: selectedConnection.cron_schedule || undefined
                                        });
                                        setShowScheduleDialog(true);
                                    }}
                                >
                                    <Pencil className="h-3 w-3" />
                                </Button>
                            </div>
                            <div className="flex items-center">
                                <Clock className={cn(
                                    "w-5 h-5 mr-2",
                                    isDark ? "text-gray-400" : "text-gray-500"
                                )} />
                                <div>
                                    {selectedConnection.cron_schedule ? (
                                        <div className="text-lg font-medium">
                                            {nextRunTime ? `Due in ${nextRunTime}` : 'Scheduled'}
                                        </div>
                                    ) : (
                                        <div className="text-lg font-medium">
                                            Manual Runs Only
                                        </div>
                                    )}
                                    <div className="text-xs opacity-70 mt-0.5">
                                        Last run: {formatTimeSince(lastSyncJob.completed_at || lastSyncJob.failed_at || lastSyncJob.created_at)}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Entity Visualization */}
                    <Card className={cn(
                        "overflow-hidden border rounded-lg",
                        isDark ? "border-gray-700/50 bg-gray-800/30" : "border-gray-200 bg-white"
                    )}>
                        <CardHeader className="p-3">
                            <div className="flex justify-between items-center">
                                <h3 className={cn(
                                    "text-base font-medium",
                                    isDark ? "text-gray-200" : "text-gray-700"
                                )}>
                                    Entity Graph
                                </h3>

                                {/* Action Buttons */}
                                <div className="flex gap-2">


                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className={cn(
                                            "h-8 gap-1.5 font-normal",
                                            isDark
                                                ? "bg-gray-700 border-gray-600 text-white"
                                                : "bg-gray-100 border-gray-200 text-gray-800"
                                        )}
                                        onClick={handleRunSync}
                                        disabled={isInitiatingSyncJob || isSyncJobRunning}
                                    >
                                        <Play className="h-3.5 w-3.5" />
                                        {isInitiatingSyncJob ? 'Starting...' : isSyncJobRunning ? 'Running...' : 'Run Sync'}
                                    </Button>
                                </div>
                            </div>

                            {/* Entity Selection Buttons - Add min-height container to prevent layout shifts */}
                            <div className="flex flex-wrap gap-1.5 mt-3 mb-1 min-h-[2.25rem] transition-all">
                                {Object.keys(stableEntityDict).length > 0 ?
                                    Object.keys(stableEntityDict)
                                        .sort() // Sort keys alphabetically
                                        .map((key) => {
                                            // Determine if this button is selected
                                            const isSelected = key === selectedEntity;

                                            return (
                                                <Button
                                                    key={key}
                                                    variant="outline"
                                                    className={cn(
                                                        "flex items-center gap-1.5 h-7 py-0 px-2 text-[13px] min-w-[90px]",
                                                        isSelected
                                                            ? isDark
                                                                ? "bg-gray-700 border-gray-600 border-[1.5px] text-white"
                                                                : "bg-gray-100 border-gray-300 border-[1.5px] text-gray-800"
                                                            : isDark
                                                                ? "bg-gray-800/80 border-gray-700/60 text-gray-300"
                                                                : "bg-white border-gray-200/80 text-gray-700"
                                                    )}
                                                    onClick={() => setSelectedEntity(key)}
                                                >
                                                    {key}
                                                    <Badge
                                                        variant="outline"
                                                        className={cn(
                                                            "ml-1 pointer-events-none text-[11px] px-1.5 font-normal h-5",
                                                            isSelected
                                                                ? isDark
                                                                    ? "bg-gray-600 text-gray-200 border-gray-500"
                                                                    : "bg-gray-200 text-gray-700 border-gray-300"
                                                                : isDark
                                                                    ? "bg-gray-700 text-gray-300 border-gray-600"
                                                                    : "bg-gray-100 text-gray-600 border-gray-200"
                                                        )}
                                                    >
                                                        {stableEntityDict[key]}
                                                    </Badge>
                                                </Button>
                                            );
                                        })
                                    : null
                                }
                            </div>
                        </CardHeader>
                        <CardContent className="p-0 pb-0">
                            {/* Flow Diagram - Add fixed height to prevent resizing during transitions */}
                            <div
                                ref={flowContainerRef}
                                className="h-[320px] w-full overflow-hidden"
                                style={{ minHeight: '320px' }}
                            >
                                <ReactFlow
                                    key={selectedConnection.id || 'no-connection'}
                                    nodes={nodes}
                                    edges={edges}
                                    onNodesChange={onNodesChange}
                                    onEdgesChange={onEdgesChange}
                                    nodeTypes={nodeTypes}
                                    fitView
                                    fitViewOptions={{
                                        padding: 0.3,
                                        minZoom: 0.1,
                                        maxZoom: 1.5,
                                        duration: 0
                                    }}
                                    onInit={setReactFlowInstance}
                                    defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
                                    style={{
                                        touchAction: 'none',
                                        cursor: 'default',
                                        background: isDark ? 'transparent' : '#fafafa'
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

                            {/* Divider between Entity Graph and Sync Progress */}
                            <div className={cn(
                                "border-t w-full mx-auto my-2",
                                isDark ? "border-gray-700/50" : "border-gray-200"
                            )} />

                            {/* Sync Progress Section */}
                            <div className="px-3 pb-3 pt-1">
                                <h3 className={cn(
                                    "text-base font-medium mb-4",
                                    isDark ? "text-gray-200" : "text-gray-700"
                                )}>
                                    Sync Progress
                                </h3>

                                {/* Normalized multi-segment progress bar - Add min-height to prevent layout shifts */}
                                <div className={cn(
                                    "relative w-full h-3 rounded-md overflow-hidden mb-6",
                                    isDark ? "bg-gray-700/50" : "bg-gray-100"
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

                                {/* Stats grid - Add min-height for containers */}
                                <div className="grid grid-cols-5 gap-3 mt-5 min-h-[5rem]">
                                    <div className={cn(
                                        "rounded-md p-3 flex flex-col items-center",
                                        isDark ? "bg-gray-700/30" : "bg-gray-50"
                                    )}>
                                        <div className="flex items-center space-x-1 mb-1">
                                            <span className="w-3 h-3 block bg-green-500 rounded-full" />
                                            <span className="text-xs font-medium">Inserted</span>
                                        </div>
                                        <span className="text-lg font-semibold">{entityData.inserted.toLocaleString()}</span>
                                    </div>

                                    <div className={cn(
                                        "rounded-md p-3 flex flex-col items-center",
                                        isDark ? "bg-gray-700/30" : "bg-gray-50"
                                    )}>
                                        <div className="flex items-center space-x-1 mb-1">
                                            <span className="w-3 h-3 block bg-cyan-500 rounded-full" />
                                            <span className="text-xs font-medium">Updated</span>
                                        </div>
                                        <span className="text-lg font-semibold">{entityData.updated.toLocaleString()}</span>
                                    </div>

                                    <div className={cn(
                                        "rounded-md p-3 flex flex-col items-center",
                                        isDark ? "bg-gray-700/30" : "bg-gray-50"
                                    )}>
                                        <div className="flex items-center space-x-1 mb-1">
                                            <span className="w-3 h-3 block bg-primary rounded-full" />
                                            <span className="text-xs font-medium">Kept</span>
                                        </div>
                                        <span className="text-lg font-semibold">{entityData.kept.toLocaleString()}</span>
                                    </div>

                                    <div className={cn(
                                        "rounded-md p-3 flex flex-col items-center",
                                        isDark ? "bg-gray-700/30" : "bg-gray-50"
                                    )}>
                                        <div className="flex items-center space-x-1 mb-1">
                                            <span className="w-3 h-3 block bg-red-500 rounded-full" />
                                            <span className="text-xs font-medium">Deleted</span>
                                        </div>
                                        <span className="text-lg font-semibold">{entityData.deleted.toLocaleString()}</span>
                                    </div>

                                    <div className={cn(
                                        "rounded-md p-3 flex flex-col items-center",
                                        isDark ? "bg-gray-700/30" : "bg-gray-50"
                                    )}>
                                        <div className="flex items-center space-x-1 mb-1">
                                            <span className="w-3 h-3 block bg-yellow-500 rounded-full" />
                                            <span className="text-xs font-medium">Skipped</span>
                                        </div>
                                        <span className="text-lg font-semibold">{entityData.skipped.toLocaleString()}</span>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
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
        </div>
    );
};

export default SourceConnectionDetailView;
