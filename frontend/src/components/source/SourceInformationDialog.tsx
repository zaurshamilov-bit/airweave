import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

interface SourceInformationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  shortName: string;
  description: string;
}

export function SourceInformationDialog({
  open,
  onOpenChange,
  name,
  shortName,
  description,
}: SourceInformationDialogProps) {
  const { resolvedTheme } = useTheme();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 flex items-center justify-center">
              <img 
                src={getAppIconUrl(shortName, resolvedTheme)} 
                alt={`${name} icon`}
                className="w-6 h-6"
              />
            </div>
            <div>
              <DialogTitle>{name}</DialogTitle>
              <DialogDescription>{description}</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold mb-2">Features</h3>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">Full Text Search</Badge>
              <Badge variant="secondary">Real-time Sync</Badge>
              <Badge variant="secondary">Metadata Extraction</Badge>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">Data Types</h3>
            <p className="text-sm text-muted-foreground">
              This source can extract and process the following types of data:
            </p>
            <ul className="list-disc list-inside mt-2 text-sm text-muted-foreground">
              <li>Documents and Files</li>
              <li>Text Content</li>
              <li>Metadata</li>
              <li>User Information</li>
            </ul>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">Documentation</h3>
            <p className="text-sm text-muted-foreground">
              For more information about this integration, visit our documentation:
            </p>
            <a 
              href={`https://docs.airweave.io/integrations/${shortName}`} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline"
            >
              View Documentation →
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}