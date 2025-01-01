import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useToast } from "@/components/ui/use-toast";
import { SyncDataSourceGrid } from "@/components/sync/SyncDataSourceGrid";
import { VectorDBSelector } from "@/components/VectorDBSelector";
import { SyncProgress } from "@/components/SyncProgress";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";

const Sync = () => {
  const [step, setStep] = useState(1);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedDB, setSelectedDB] = useState<string | null>(null);
  const location = useLocation();
  const { toast } = useToast();

  const handleSourceSelect = (sourceId: string, skipCredentials?: boolean) => {
    setSelectedSource(sourceId);
    setStep(skipCredentials ? 3 : 2);
  };

  const handleStartSync = () => {
    setStep(4);
  };

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

  return (
    <div className="container mx-auto py-8">
      <div className="mx-auto">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold">Set up your pipeline</h1>
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
            <SyncDataSourceGrid onSelect={handleSourceSelect} />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-semibold">Choose your vector database</h2>
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            </div>
            <VectorDBSelector onComplete={(dbId) => {
              setSelectedDB(dbId);
              setStep(3);
            }} />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold">Ready to sync</h2>
              <p className="text-muted-foreground mt-2">Your pipeline is configured and ready to start syncing</p>
            </div>
            <div className="flex justify-center">
              <Button size="lg" onClick={handleStartSync}>
                Start Sync
              </Button>
            </div>
          </div>
        )}

        {step === 4 && <SyncProgress />}
      </div>
    </div>
  );
};

export default Sync;
