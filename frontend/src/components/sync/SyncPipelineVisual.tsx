import { Card } from "@/components/ui/card";
import { getAppIconUrl, getDestinationIconUrl } from "@/lib/utils/icons";
import { ArrowRight } from "lucide-react";
import { SyncDetailsData } from "./types";

interface SyncPipelineVisualProps {
  sync: SyncDetailsData;
}

export const SyncPipelineVisual = ({ sync }: SyncPipelineVisualProps) => {
  const { source, destination } = sync.uiMetadata;

  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-6">Pipeline Configuration</h2>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-lg bg-secondary-100 bg-opacity-50 border border-secondary-200 flex items-center justify-center">
            <img 
              src={getAppIconUrl(source.shortName)} 
              alt={`${source.name} icon`}
              className="w-8 h-8"
            />
          </div>
          <div>
            <p className="font-medium">{source.name}</p>
            <p className="text-sm text-muted-foreground capitalize">Source</p>
          </div>
        </div>
        <ArrowRight className="h-8 w-8 text-muted-foreground" />
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-lg bg-secondary-100 bg-opacity-50 border border-secondary-200 flex items-center justify-center">
            <img 
              src={getDestinationIconUrl(destination.shortName)} 
              alt={`${destination.name} icon`}
              className="w-8 h-8"
            />
          </div>
          <div>
            <p className="font-medium">{destination.name}</p>
            <p className="text-sm text-muted-foreground capitalize">Destination</p>
          </div>
        </div>
      </div>
    </Card>
  );
};