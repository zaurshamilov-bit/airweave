import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { toast, useToast } from "@/components/ui/use-toast";
import { SyncDataSourceGrid } from "@/components/sync/SyncDataSourceGrid";
import { VectorDBSelector } from "@/components/VectorDBSelector";
import { SyncProgress } from "@/components/SyncProgress";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useSyncSubscription } from "@/hooks/useSyncSubscription";

/**
 * This component coordinates all user actions (source selection,
 * vector DB selection, sync creation, and sync job triggering).
 * It uses local React state, but you can integrate any data-fetching
 * or global state libraries (e.g., React Query, Redux, Zustand).
 */

interface ConnectionSelection {
  connectionId: string;
  isNative?: boolean;
}

const Sync = () => {
  // Which setup step are we on?
  const [step, setStep] = useState<number>(1);

  // Chosen data source (step 1 -> 2)
  const [selectedSource, setSelectedSource] = useState<ConnectionSelection | null>(null);

  // Chosen vector DB or native indexing (step 2 -> 3)
  const [selectedDB, setSelectedDB] = useState<ConnectionSelection | null>(null);

  // Created sync ID and job ID once we make calls
  const [syncId, setSyncId] = useState<string | null>(null);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);

  // Hook for showing user feedback toasts
  const { toast } = useToast();
  const location = useLocation();

  // Subscribe to SSE updates whenever syncJobId is set
  // 'updates' returns an array of progress updates
  const updates = useSyncSubscription(syncJobId);

  /**
   * Notify the user if they've just returned from an oauth2 flow.
   */
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const connectedStatus = query.get("connected");
    if (connectedStatus === "success") {
      toast({
        title: "Connection successful",
        description: "Your data source is now connected."
      });
    } else if (connectedStatus === "error") {
      toast({
        variant: "destructive",
        title: "Connection failed",
        description: "There was an error connecting to your data source."
      });
    }
  }, [location.search, toast]);

  /**
   * handleSourceSelect is triggered by SyncDataSourceGrid when the user
   * chooses a data source. We move from step 1 -> 2 to pick vector DB.
   */
  const handleSourceSelect = async (connectionId: string) => {
    setSelectedSource({ connectionId });
    setStep(2);
  };

  /**
   * handleVectorDBSelected is triggered after the user chooses a vector DB.
   * We move from step 2 -> 3 to confirm the pipeline.
   */
  const handleVectorDBSelected = async (dbDetails: ConnectionSelection) => {
    setSelectedDB(dbDetails);
    setStep(3);
  };

  /**
   * createNewSync calls the backend to create a Sync resource.
   * We won't run immediately here; we'll call /run afterwards for clarity.
   */
  const createNewSync = async () => {
    if (!selectedSource || !selectedDB) return null;

    try {
      const resp = await apiClient.post("/sync/", {
        name: "Sync from UI",
        source_connection_id: selectedSource.connectionId,
        // If the user picked a "non-native" DB, we pass it along
        ...(selectedDB.isNative ? {} : { destination_connection_id: selectedDB.connectionId }),
        run_immediately: false
      });
      if (!resp.ok) {
        throw new Error("Failed to create sync");
      }
      const data = await resp.json();
      setSyncId(data.id);
      return data.id as string;
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Sync creation failed",
        description: err.message || String(err)
      });
      return null;
    }
  };

  /**
   * runSync calls the backend to start a sync job
   * (POST /sync/{sync_id}/run).
   */
  const runSync = async (syncIdToRun: string) => {
    try {
      const resp = await apiClient.post(`/sync/${syncIdToRun}/run`);
      if (!resp.ok) {
        throw new Error("Failed to run sync job");
      }
      const data = await resp.json();
      // Store the job ID so SSE subscription can begin
      setSyncJobId(data.id);
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Sync job start failed",
        description: err.message || String(err)
      });
    }
  };

  /**
   * handleStartSync creates the new Sync if necessary,
   * then runs it, and moves to step 4 for progress updates.
   */
  const handleStartSync = async () => {
    // If we haven't created a sync yet, do so now
    let createdSyncId = syncId;
    if (!createdSyncId) {
      createdSyncId = await createNewSync();
    }

    if (createdSyncId) {
      await runSync(createdSyncId);
      setStep(4);
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mx-auto">
        {/* Step + progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold">
              Set up your pipeline
            </h1>
            <div className="text-sm text-muted-foreground">
              Step {step} of 4
            </div>
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-secondary/20">
            <div
              className="h-2 rounded-full bg-primary transition-all duration-300"
              style={{ width: `${(step / 4) * 100}%` }}
            />
          </div>
        </div>

        {/* Step 1: Pick data source */}
        {step === 1 && (
          <div className="space-y-6">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-semibold">Choose your data source</h2>
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            </div>
            <SyncDataSourceGrid onSelect={handleSourceSelect} />
          </div>
        )}

        {/* Step 2: Pick vector DB */}
        {step === 2 && (
          <div className="space-y-6">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-semibold">Choose your vector database</h2>
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            </div>
            <VectorDBSelector onComplete={handleVectorDBSelected} />
          </div>
        )}

        {/* Step 3: Confirm and start sync */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold">Ready to sync?</h2>
              <p className="text-muted-foreground mt-2">
                Your pipeline is configured and ready to start syncing.
              </p>
            </div>
            <div className="flex justify-center">
              <Button size="lg" onClick={handleStartSync}>
                Start Sync
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Show progress updates */}
        {step === 4 && (
          <div className="space-y-6">
            <SyncProgress syncId={syncId} syncJobId={syncJobId} />
          </div>
        )}
      </div>
    </div>
  );
};

export default Sync;
