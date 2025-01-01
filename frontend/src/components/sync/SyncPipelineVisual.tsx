import { Card } from "@/components/ui/card";
import { getAppIconUrl, getDestinationIconUrl } from "@/lib/utils/icons";
import { Database, ArrowRight } from "lucide-react";

interface SyncPipelineVisualProps {
  sync: any; // Replace with proper type
}

export const SyncPipelineVisual = ({ sync }: SyncPipelineVisualProps) => {
  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-6">Pipeline Configuration</h2>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="h-16   w-16 rounded-lg bg-secondary-100 bg-opacity-50 border border-secondary-200 flex items-center justify-center">
            <img 
              src={getAppIconUrl(sync.metadata.source.shortName)} 
              alt={`${sync.metadata.source.name} icon`}
              className="w-8 h-8"
            />
          </div>
          <div>
            <p className="font-medium">{sync.metadata.source.name}</p>
            <p className="text-sm text-muted-foreground">Source</p>
          </div>
        </div>
        <ArrowRight className="h-8 w-8 text-muted-foreground" />
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-lg bg-secondary-100 bg-opacity-50 border border-secondary-200 flex items-center justify-center">
            <img 
              src={getDestinationIconUrl(sync.metadata.destination.shortName)} 
              alt={`${sync.metadata.destination.name} icon`}
              className="w-8 h-8"
            />
          </div>
          <div>
            <p className="font-medium">{sync.metadata.destination.name}</p>
            <p className="text-sm text-muted-foreground">Destination</p>
          </div>
        </div>
      </div>
    </Card>
  );
};