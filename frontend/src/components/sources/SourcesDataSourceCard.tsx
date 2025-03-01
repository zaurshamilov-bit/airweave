import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppIconUrl } from "@/lib/utils/icons";
import { ManageSourceDialog } from "./ManageSourceDialog";
import { useState } from "react";
import { Connection } from "@/types";
import { CircleDot } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";

interface SourcesDataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onConnect: () => void;
  connections: Connection[];
}

export function SourcesDataSourceCard({ 
  shortName, 
  name, 
  description, 
  status,
  onConnect,
  connections,
}: SourcesDataSourceCardProps) {
  const [showManageDialog, setShowManageDialog] = useState(false);
  const { resolvedTheme } = useTheme();
  const activeConnections = connections.filter(conn => conn.status === "active");

  return (
    <>
      <Card className="w-full min-h-[240px] flex flex-col justify-between overflow-hidden">
        <CardHeader className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start space-x-3 flex-1 min-w-0">
              <div className="w-8 h-8 shrink-0 flex items-center justify-center">
                <img 
                  src={getAppIconUrl(shortName, resolvedTheme)} 
                  alt={`${name} icon`}
                  className="w-6 h-6"
                />
              </div>
              <div className="min-w-0 flex-1">
                <CardTitle className="text-lg mb-1 line-clamp-1">{name}</CardTitle>
                <CardDescription className="line-clamp-2">{description}</CardDescription>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-0 flex-grow">
          {status === "connected" && (
            <div className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium",
              "bg-primary/10 text-primary"
            )}>
              <CircleDot className="w-3 h-3" />
              {activeConnections.length} active connection{activeConnections.length !== 1 ? 's' : ''}
            </div>
          )}
          <p className="text-sm text-muted-foreground line-clamp-3 mt-2">
            Extract and sync your {name} data to your vector database of choice.
          </p>
        </CardContent>
        <CardFooter className="p-4 pt-0">
          <Button 
            onClick={() => setShowManageDialog(true)} 
            variant={status === "connected" ? "secondary" : "default"} 
            className="w-full"
          >
            Manage Source
          </Button>
        </CardFooter>
      </Card>

      <ManageSourceDialog
        open={showManageDialog}
        onOpenChange={setShowManageDialog}
        name={name}
        shortName={shortName}
        description={description}
        onConnect={onConnect}
        existingConnections={connections}
        isLoading={false}
      />
    </>
  );
}