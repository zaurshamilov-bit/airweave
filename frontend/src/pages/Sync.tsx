import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useToast } from "@/components/ui/use-toast";
import { SyncDataSourceGrid } from "@/components/sync/SyncDataSourceGrid";
import { VectorDBSelector } from "@/components/VectorDBSelector";
import { SyncProgress } from "@/components/SyncProgress";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";

/**
 * This component coordinates all user actions (source selection, 
 * vector DB selection, sync creation, and sync job triggering).
 * It uses straightforward local state, but you can extract or 
 * replace this with global store (Redux, Zustand, etc.) or React Query 
 * if you prefer a different pattern.
 */

const Sync = () => {
  const [step, setStep] = useState<number>(1);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedDB, setSelectedDB] = useState<string | null>(null);

  // Store the newly created sync ID (after POST /sync/) and the job ID (after POST /sync/{id}/run).
  const [syncId, setSyncId] = useState<string | null>(null);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);

  const location = useLocation();
  const { toast } = useToast();

  // If a user returns from an oauth2 or other service, we show success/failure toasts
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const connectedStatus = query.get("connected");
    if (connectedStatus === "success") {
      toast({
        title: "Connection successful",
        description: "Your data source is now connected.",
      });
    } else if (connectedStatus === "error") {
      toast({
        variant: "destructive",
        title: "Connection failed",
        description: "There was an error connecting to your data source.",
      });
    }
  }, [location.search, toast]);

  /**
   * handleSourceSelect is triggered by SyncDataSourceGrid when the user
   * chooses a data source. We always want to go to step 2 (vector DB selection)
   * when a source is selected.
   */
  const handleSourceSelect = async (sourceId: string) => {
    setSelectedSource(sourceId);
    // Always go to step 2 (vector DB selection)
    setStep(2);
  };

  /**
   * handleVectorDBSelected sets the selected vector DB.
   * Once the user confirms, we move to step 3 (confirm + create sync).
   */
  const handleVectorDBSelected = async (dbId: string) => {
    setSelectedDB(dbId);
    setStep(3);
  };

  /**
   * createNewSync calls the backend to create a Sync resource.
   */
  const createNewSync = async () => {
    // Example payload with minimal fields required by /sync/:
    // (See the openapi: SyncCreate requires { name, source_connection_id }, etc.)
    if (!selectedSource) return;
    if (!selectedDB) return;

    try {
      const resp = await fetch("http://localhost:8001/sync/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
          // If you want to pass x-api-key or any auth header:
          // "x-api-key": "someKeyValue"
        },
        body: JSON.stringify({
          name: "My Sync from UI",
          source_connection_id: selectedSource,
          destination_connection_id: selectedDB,
          run_immediately: false
        }),
      });
      if (!resp.ok) {
        throw new Error("Failed to create sync");
      }
      const data = await resp.json();
      setSyncId(data.id);
      return data.id;
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Sync creation failed",
        description: err.message || String(err),
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
      const resp = await fetch(`/sync/${syncIdToRun}/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        }
      });
      if (!resp.ok) {
        throw new Error("Failed to run sync job");
      }
      const data = await resp.json();
      // The returned object is a SyncJob, which has an "id"
      setSyncJobId(data.id);
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Sync job start failed",
        description: err.message || String(err),
      });
    }
  };

  /**
   * handleStartSync creates the sync in the backend,
   * then runs it, then proceeds to step 4 for progress.
   */
  const handleStartSync = async () => {
    // If we haven't created a sync yet, do so
    let createdId = syncId;
    if (!createdId) {
      createdId = await createNewSync();
    }

    if (createdId) {
      await runSync(createdId);
      setStep(4);
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mx-auto">
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

        {step === 1 && (
          <div className="space-y-6">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-semibold">Choose your data source</h2>
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            </div>
            {/* 
              SyncDataSourceGrid should fetch and display available
              sources or existing connections, then call onSelect(sourceId, skipCredentials?)
              to progress the flow. 
            */}
            <SyncDataSourceGrid onSelect={handleSourceSelect} />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-semibold">Choose your vector database</h2>
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            </div>
            {/* 
              VectorDBSelector should fetch and display possible vector DB 
              destinations, then call onComplete(dbId) 
            */}
            <VectorDBSelector onComplete={handleVectorDBSelected} />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold">Ready to sync</h2>
              <p className="text-muted-foreground mt-2">
                Your pipeline is configured and ready to start syncing
              </p>
            </div>
            <div className="flex justify-center">
              <Button size="lg" onClick={handleStartSync}>
                Start Sync
              </Button>
            </div>
          </div>
        )}

        {step === 4 && (
          // SyncProgress can poll the job status by referencing syncId and syncJobId.
          // For example:
          <SyncProgress 
            syncId={syncId} 
            syncJobId={syncJobId}
          />
        )}
      </div>
    </div>
  );
};

export default Sync;
