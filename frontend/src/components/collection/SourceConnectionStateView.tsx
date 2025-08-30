// components/collection/SourceConnectionStateView.tsx
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { EntityStateMediator } from '@/services/entityStateMediator';
import { useEntityStateStore } from '@/stores/entityStateStore';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Loader2, AlertCircle, RefreshCw, Clock, X, History } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import { SourceConnectionSettings } from './SourceConnectionSettings';
import { EntityStateList } from './EntityStateList';
import { SyncErrorCard } from './SyncErrorCard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Source Connection interface - matches backend schema
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
  white_label_id?: string;
  created_by_email: string;
  modified_by_email: string;
  auth_fields?: Record<string, any> | string;
  status?: string;
  latest_sync_job_status?: string;
  latest_sync_job_id?: string;
  latest_sync_job_started_at?: string;
  latest_sync_job_completed_at?: string;
  latest_sync_job_error?: string;
  cron_schedule?: string;
  next_scheduled_run?: string;
  auth_provider?: string;
  auth_provider_config?: Record<string, any>;
}

interface Props {
  sourceConnectionId: string;
  onConnectionDeleted?: () => void;
}

const SourceConnectionStateView: React.FC<Props> = ({ sourceConnectionId, onConnectionDeleted }) => {
  const [isInitializing, setIsInitializing] = useState(true);
  const [sourceConnection, setSourceConnection] = useState<SourceConnection | null>(null);
  const [isRunningSync, setIsRunningSync] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [nextRunTime, setNextRunTime] = useState<string | null>(null);
  const [lastRanDisplay, setLastRanDisplay] = useState<string>('Never');

  const mediator = useRef<EntityStateMediator | null>(null);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Direct store subscription - single source of truth
  const state = useEntityStateStore(
    store => store.getEntityState(sourceConnectionId)
  );

  // Format time ago display
  const formatTimeAgo = useCallback((dateStr: string | undefined) => {
    if (!dateStr) return 'Never';

    // CRITICAL: Backend sends naive datetime strings WITHOUT timezone
    // These are actually UTC times but JavaScript interprets them as LOCAL time by default!
    // Check if it already has timezone info (Z, +, or - but not in the date part like 2024-01-15)
    const hasTimezone = dateStr.endsWith('Z') ||
                       dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);

    const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;

    const date = new Date(utcDateStr);
    const now = new Date();

    // Now both dates are properly parsed and comparison is correct
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays > 0) {
      return `${diffDays}d ago`;
    } else if (diffHrs > 0) {
      return `${diffHrs}h ago`;
    } else if (diffMins > 0) {
      return `${diffMins}m ago`;
    } else {
      return 'Just now';
    }
  }, []);

  // Format exact timestamp for tooltip
  const formatExactTime = useCallback((dateStr: string | undefined) => {
    if (!dateStr) return 'Never';

    // Backend sends naive datetime strings that are actually UTC
    // We need to interpret them as UTC, not local time
    const hasTimezone = dateStr.endsWith('Z') ||
                       dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);

    const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;

    const date = new Date(utcDateStr);

    // Format in user's local timezone with clear indication
    const localTime = date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });

    // Also show UTC time for clarity
    const utcTime = date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short'
    });

    // Return both times if they're different
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (userTimezone === 'UTC') {
      return localTime;
    } else {
      return `${localTime}`;  // Just show local time, it already includes timezone
    }
  }, []);

  // Calculate next run time from cron expression
  const calculateNextRunTime = useCallback((cronExpression: string | null) => {
    if (!cronExpression) return null;

    try {
      const parts = cronExpression.split(' ');
      if (parts.length !== 5) return null;

      const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
      const now = new Date();

      // Create next run date in UTC since cron expressions are typically in UTC
      const nextRun = new Date(now);

      // Simplified calculation for daily schedules
      if (hour !== '*' && dayOfMonth === '*' && dayOfWeek === '*') {
        const targetHour = parseInt(hour);
        const targetMinute = parseInt(minute) || 0;

        // Set the UTC time for next run
        nextRun.setUTCHours(targetHour, targetMinute, 0, 0);

        // If the time has already passed today, move to tomorrow
        if (nextRun <= now) {
          nextRun.setUTCDate(nextRun.getUTCDate() + 1);
        }
      }

      // Calculate time difference from now
      const diffMs = nextRun.getTime() - now.getTime();
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (diffHrs > 0) {
        return `${diffHrs}h ${diffMins}m`;
      } else if (diffMins > 0) {
        return `${diffMins}m`;
      } else {
        return 'Soon';
      }
    } catch (error) {
      console.error("Error calculating next run time:", error);
      return null;
    }
  }, []);

  // Fetch source connection details
  const fetchSourceConnection = useCallback(async () => {
    try {
      const response = await apiClient.get(`/source-connections/${sourceConnectionId}`);
      if (response.ok) {
        const data = await response.json();
        setSourceConnection(data);

        // Calculate next run time
        if (data.cron_schedule) {
          const nextRun = calculateNextRunTime(data.cron_schedule);
          setNextRunTime(nextRun);
        }
      }
    } catch (error) {
      console.error('Failed to fetch source connection:', error);
    }
  }, [sourceConnectionId, calculateNextRunTime]);

  useEffect(() => {
    // Initialize state mediator
    mediator.current = new EntityStateMediator(sourceConnectionId);

    Promise.all([
      mediator.current.initialize(),
      fetchSourceConnection()
    ]).then(() => {
      setIsInitializing(false);
    }).catch(error => {
      console.error('Failed to initialize:', error);
      setIsInitializing(false);
    });

    return () => {
      mediator.current?.cleanup();
    };
  }, [sourceConnectionId, fetchSourceConnection]);

  // Update next run time when cron_schedule changes
  useEffect(() => {
    if (sourceConnection?.cron_schedule) {
      const nextRun = calculateNextRunTime(sourceConnection.cron_schedule);
      setNextRunTime(nextRun);
    } else {
      setNextRunTime(null);
    }
  }, [sourceConnection?.cron_schedule, calculateNextRunTime]);

  // Update last ran display
  useEffect(() => {
    const updateLastRan = () => {
      // If a sync is currently running, show "Running now"
      if (state?.syncStatus === 'in_progress' || state?.syncStatus === 'pending') {
        setLastRanDisplay('Running now');
      } else if (sourceConnection?.latest_sync_job_started_at) {
        setLastRanDisplay(formatTimeAgo(sourceConnection.latest_sync_job_started_at));
      } else {
        setLastRanDisplay('Never');
      }
    };

    updateLastRan();
    // Update every minute to keep the display fresh
    const interval = setInterval(updateLastRan, 60000);

    return () => clearInterval(interval);
  }, [sourceConnection?.latest_sync_job_started_at, state?.syncStatus, formatTimeAgo]);

  // Clear cancelling state when sync status changes to cancelled
  useEffect(() => {
    if (state?.syncStatus === 'cancelled' && isCancelling) {
      setIsCancelling(false);
      toast({
        title: "Sync Cancelled",
        description: "The sync job has been successfully cancelled.",
      });
    }
  }, [state?.syncStatus, isCancelling]);

  // Refetch source connection when sync fails to get latest error details
  useEffect(() => {
    if (state?.syncStatus === 'failed' || state?.error) {
      // Refetch to get the latest_sync_job_error from backend
      fetchSourceConnection();
    }
  }, [state?.syncStatus, state?.error, fetchSourceConnection]);

  const handleRunSync = async () => {
    try {
      setIsRunningSync(true);
      const response = await apiClient.post(`/source-connections/${sourceConnectionId}/run`);
      if (response.ok) {
        const syncJob = await response.json();
        toast({
          title: "Sync started",
          description: "The sync has been started successfully"
        });

        // Let the mediator handle the state transition
        if (mediator.current && syncJob.id) {
          await mediator.current.subscribeToJobUpdates(syncJob.id);
        }
        // Clear isRunningSync once the sync has actually started
        setIsRunningSync(false);
      } else {
        throw new Error("Failed to start sync");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to start sync",
        variant: "destructive"
      });
      setIsRunningSync(false);
    }
  };

  const handleCancelSync = async () => {
    // Use currentJobId from state if available, otherwise try syncId
    const jobId = state?.currentJobId || state?.syncId;

    if (!jobId) {
      toast({
        title: "Error",
        description: "No active sync job to cancel",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsCancelling(true);
      console.log(`Cancelling sync job ${jobId} for connection ${sourceConnectionId}`);
      const response = await apiClient.post(`/source-connections/${sourceConnectionId}/jobs/${jobId}/cancel`);

      if (response.ok) {
        toast({
          title: "Cancellation Requested",
          description: "The sync is being cancelled. This may take a moment to complete.",
        });
        // Don't clear isCancelling here - it will be cleared when we detect the status change
      } else {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to cancel sync job");
      }
    } catch (error) {
      console.error("Error cancelling sync:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to cancel sync job",
        variant: "destructive"
      });
      setIsCancelling(false);
    }
  };

  const handleConnectionUpdate = (updatedConnection: SourceConnection) => {
    setSourceConnection(updatedConnection);
    // Re-fetch to ensure everything is in sync
    fetchSourceConnection();
  };

  if (isInitializing && !state) {
    return (
      <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground">Loading entity state...</p>
      </div>
    );
  }

  // Sync states - match backend SyncJobStatus enum
  const isRunning = state?.syncStatus === 'in_progress';
  const isPending = state?.syncStatus === 'pending';
  const isSyncing = isRunning || isPending;

  // Get sync status display
  const getSyncStatusDisplay = () => {
    if (state?.syncStatus === 'failed') return { text: 'Failed', color: 'bg-red-500' };
    if (state?.syncStatus === 'completed') return { text: 'Completed', color: 'bg-green-500' };
    if (isRunning) return { text: 'Running', color: 'bg-blue-500 animate-pulse' };
    if (isPending) return { text: 'Pending', color: 'bg-yellow-500 animate-pulse' };
    return { text: 'Ready', color: 'bg-gray-400' };
  };

  const syncStatus = getSyncStatusDisplay();

  return (
    <div className="space-y-4">
      {/* Status Dashboard with Settings - All in one row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 flex-wrap items-center">
          {/* Entities Card */}
          <div className={cn(
            "rounded-lg p-3 flex items-center gap-2 shadow-sm transition-all duration-200 h-10 min-w-[100px]",
            isDark
              ? "bg-gray-800/60 border border-gray-700/50"
              : "bg-white border border-gray-100"
          )}>
            <div className="text-xs uppercase tracking-wider font-medium opacity-60">
              Entities
            </div>
            <div className="text-base font-semibold">
              {state?.totalEntities.toLocaleString() || 0}
            </div>
          </div>

          {/* Status Card */}
          <div className={cn(
            "rounded-lg p-3 flex items-center gap-2 shadow-sm transition-all duration-200 h-10 min-w-[110px]",
            isDark
              ? "bg-gray-800/60 border border-gray-700/50"
              : "bg-white border border-gray-100"
          )}>
            <div className="text-xs uppercase tracking-wider font-medium opacity-60">
              Status
            </div>
            <div className="text-base font-medium flex items-center gap-1">
              <span className={`inline-flex h-2 w-2 rounded-full ${syncStatus.color}`} />
              <span className="capitalize text-xs">{syncStatus.text}</span>
            </div>
          </div>

          {/* Schedule Card */}
          <div className={cn(
            "rounded-lg p-3 flex items-center gap-2 shadow-sm transition-all duration-200 h-10 min-w-[120px]",
            isDark
              ? "bg-gray-800/60 border border-gray-700/50"
              : "bg-white border border-gray-100"
          )}>
            <div className="text-xs uppercase tracking-wider font-medium opacity-60">
              Schedule
            </div>
            <div className="flex items-center gap-1">
              <Clock className={cn(
                "w-4 h-4",
                isDark ? "text-gray-400" : "text-gray-500"
              )} />
              <div className="text-base font-medium pl-1">
                {sourceConnection?.cron_schedule ?
                  (nextRunTime ? `In ${nextRunTime}` : 'Scheduled') :
                  'Manual'}
              </div>
            </div>
          </div>

          {/* Last Ran Badge */}
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className={cn(
                  "rounded-lg p-3 flex items-center gap-2 shadow-sm transition-all duration-200 h-10 min-w-[120px] cursor-help",
                  // Highlight when sync is running
                  (state?.syncStatus === 'in_progress' || state?.syncStatus === 'pending')
                    ? isDark
                      ? "bg-blue-900/30 border border-blue-700/50"
                      : "bg-blue-50 border border-blue-200"
                    : isDark
                      ? "bg-gray-800/60 border border-gray-700/50"
                      : "bg-white border border-gray-100"
                )}>
                  <div className="text-xs uppercase tracking-wider font-medium opacity-60">
                    Last Sync
                  </div>
                  <div className="flex items-center gap-1">
                    {(state?.syncStatus === 'in_progress' || state?.syncStatus === 'pending') ? (
                      <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                    ) : (
                      <History className={cn(
                        "w-4 h-4",
                        isDark ? "text-gray-400" : "text-gray-500"
                      )} />
                    )}
                    <div className={cn(
                      "text-base font-medium pl-1",
                      (state?.syncStatus === 'in_progress' || state?.syncStatus === 'pending') && "text-blue-600 dark:text-blue-400"
                    )}>
                      {lastRanDisplay}
                    </div>
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">
                  {state?.syncStatus === 'in_progress' || state?.syncStatus === 'pending'
                    ? 'Sync is currently running'
                    : formatExactTime(sourceConnection?.latest_sync_job_started_at)}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Settings and Action Buttons */}
        <div className="flex gap-2 items-center">
          {/* Refresh/Cancel Button - Square button that transforms */}
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className={cn(
                    "h-10 w-10 rounded-lg shadow-sm transition-all duration-200",
                    isSyncing
                      ? isCancelling
                        ? isDark
                          ? "bg-orange-900/30 border-orange-700 hover:bg-orange-900/50 cursor-not-allowed"
                          : "bg-orange-50 border-orange-200 hover:bg-orange-100 cursor-not-allowed"
                        : isDark
                          ? "bg-red-900/30 border-red-700 hover:bg-red-900/50 cursor-pointer"
                          : "bg-red-50 border-red-200 hover:bg-red-100 cursor-pointer"
                      : isRunningSync
                        ? isDark
                          ? "bg-gray-800/50 border-gray-700/50 cursor-not-allowed"
                          : "bg-gray-50 border-gray-200 cursor-not-allowed"
                        : isDark
                          ? "bg-gray-800/60 border-gray-700/50 hover:bg-gray-700 cursor-pointer"
                          : "bg-white border-gray-100 hover:bg-gray-50 cursor-pointer"
                  )}
                  onClick={isSyncing ? handleCancelSync : handleRunSync}
                  disabled={isRunningSync || isCancelling}
                >
                  {isSyncing ? (
                    isCancelling ? (
                      <Loader2 className="h-4 w-4 animate-spin text-orange-500" />
                    ) : (
                      <X className="h-4 w-4 text-red-500" />
                    )
                  ) : (
                    <RefreshCw className={cn(
                      "h-4 w-4",
                      isRunningSync && "animate-spin",
                      isDark ? "text-gray-400" : "text-gray-600"
                    )} />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">
                  {isSyncing
                    ? isCancelling
                      ? "Cancelling sync..."
                      : "Cancel sync"
                    : isRunningSync
                      ? "Starting sync..."
                      : "Refresh data"}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Settings Menu */}
          {sourceConnection && (
            <div className={cn(
              "rounded-lg p-1 shadow-sm transition-all duration-200 h-10 flex items-center justify-center",
              isDark
                ? "bg-gray-800/60 border border-gray-700/50"
                : "bg-white border border-gray-100"
            )}>
              <SourceConnectionSettings
                sourceConnection={sourceConnection}
                onUpdate={handleConnectionUpdate}
                onDelete={onConnectionDeleted}
                isDark={isDark}
                resolvedTheme={resolvedTheme}
              />
            </div>
          )}
        </div>
      </div>

      {/* Show error card if sync failed or there's an error */}
      {((state?.error || state?.syncStatus === 'failed') && state?.syncStatus !== 'cancelled') && (
        <SyncErrorCard
          error={state?.error || sourceConnection?.latest_sync_job_error || "The last sync failed. Check the logs for more details."}
          isDark={isDark}
        />
      )}

      {/* Always show Entity State List */}
      <EntityStateList
        state={state}
        sourceShortName={sourceConnection?.short_name || ''}
        isDark={isDark}
        onStartSync={handleRunSync}
        isRunning={isRunning}
        isPending={isPending}
      />
    </div>
  );
};

export default SourceConnectionStateView;
