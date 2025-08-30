// components/collection/SourceConnectionStateView.tsx
import React, { useEffect, useState, useRef } from 'react';
import { EntityStateMediator } from '@/services/entityStateMediator';
import { useEntityStateStore, EntityState } from '@/stores/entityStateStore';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Loader2, AlertCircle, Plus, RefreshCw } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from '@/hooks/use-toast';

interface Props {
  sourceConnectionId: string;
}

interface EntityRowProps {
  name: string;
  count: number;
  isSelected: boolean;
  onClick: () => void;
  isAnimating: boolean;
}

const EntityRow: React.FC<EntityRowProps> = ({ name, count, isSelected, onClick, isAnimating }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  return (
    <div
      className={cn(
        "flex items-center justify-between px-3 py-2 rounded-md cursor-pointer transition-all",
        isSelected
          ? "bg-primary/10 border border-primary"
          : isDark
            ? "hover:bg-gray-800"
            : "hover:bg-gray-50",
        isAnimating && "animate-pulse"
      )}
      onClick={onClick}
    >
      <span className="font-medium">{name}</span>
      <span className={cn(
        "text-sm",
        isDark ? "text-gray-400" : "text-gray-600"
      )}>{count.toLocaleString()}</span>
    </div>
  );
};

const SourceConnectionStateView: React.FC<Props> = ({ sourceConnectionId }) => {
  const [isInitializing, setIsInitializing] = useState(true);
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const mediator = useRef<EntityStateMediator | null>(null);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Direct store subscription - single source of truth
  const state = useEntityStateStore(
    store => store.getEntityState(sourceConnectionId)
  );

  useEffect(() => {
    // Initialize state mediator
    mediator.current = new EntityStateMediator(sourceConnectionId);

    mediator.current.initialize().then(() => {
      setIsInitializing(false);
    }).catch(error => {
      console.error('Failed to initialize mediator:', error);
      setIsInitializing(false);
    });

    return () => {
      mediator.current?.cleanup();
    };
  }, [sourceConnectionId]);

  const handleRefresh = async () => {
    try {
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
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to start sync",
        variant: "destructive"
      });
    }
  };

  if (isInitializing && !state) {
    return (
      <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground">Loading entity state...</p>
      </div>
    );
  }

  // Error state
  if (state?.syncStatus === 'failed') {
    return (
      <Card className={cn(
        "border-2 border-orange-400",
        isDark ? "bg-gray-800/30" : ""
      )}>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500" />
            <h3 className="text-lg font-semibold">Sync Error</h3>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            {state.error || "An error occurred during the last sync"}
          </p>
          <Button onClick={handleRefresh} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry Sync
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Sync states - match backend SyncJobStatus enum
  const isRunning = state?.syncStatus === 'in_progress';
  const isPending = state?.syncStatus === 'pending';
  const isSyncing = isRunning || isPending;

  return (
    <div className="space-y-4">
      {/* Status Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Entity State</h3>
          {isPending && (
            <Badge variant="secondary" className="animate-pulse">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Preparing
            </Badge>
          )}
          {isRunning && (
            <Badge variant="default" className="animate-pulse">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Syncing
            </Badge>
          )}
        </div>
        <Button
          onClick={handleRefresh}
          variant="outline"
          size="sm"
          disabled={isSyncing}
        >
          <RefreshCw className={cn(
            "h-4 w-4 mr-1",
            isSyncing && "animate-spin"
          )} />
          Refresh
        </Button>
      </div>

      {/* Entity List Card */}
      <Card className={cn(
        isRunning && "border-2 border-dashed border-blue-400",
        isPending && "border-2 border-dashed border-yellow-400",
        isDark ? "bg-gray-800/30 border-gray-700/50" : "bg-white"
      )}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h4 className="text-md font-medium">Entities from this source</h4>
            <span className="text-sm text-muted-foreground">
              Total: {state?.totalEntities.toLocaleString() || 0}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {state?.entityCounts && Object.keys(state.entityCounts).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(state.entityCounts).map(([name, count]) => (
                <EntityRow
                  key={name}
                  name={name}
                  count={count}
                  isSelected={selectedEntity === name}
                  onClick={() => setSelectedEntity(name)}
                  isAnimating={isSyncing && Math.random() > 0.8}
                />
              ))}

              {/* Total Row */}
              <div className="pt-2 mt-2 border-t">
                <div className="flex justify-between font-semibold">
                  <span>Total</span>
                  <span>{state.totalEntities.toLocaleString()}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className={cn(
              "text-center py-8",
              isDark ? "text-gray-400" : "text-muted-foreground"
            )}>
              <p className="mb-4">No entities synced yet</p>
              <Button onClick={handleRefresh} variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                Start Initial Sync
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Selected Entity Details (placeholder for future enhancement) */}
      {selectedEntity && (
        <Card className={cn(
          isDark ? "bg-gray-800/30 border-gray-700/50" : "bg-white"
        )}>
          <CardHeader>
            <h4 className="text-md font-medium">{selectedEntity} Details</h4>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Entity schema and sample data will be displayed here
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SourceConnectionStateView;
