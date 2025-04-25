import { useState, useEffect } from "react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, ExternalLink, Database } from "lucide-react";
import { CodeBlock } from "@/components/ui/code-block";
import { apiClient } from "@/lib/api";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { useNavigate } from "react-router-dom";

interface SyncCardProps {
  syncId: string;
  syncName: string;
  sourceConnectionShortName: string;
  status: string;
  onViewDetails?: () => void;
  onChat?: () => void;
}

export function SyncCard({
  syncId,
  syncName,
  sourceConnectionShortName,
  status,
  onViewDetails,
  onChat,
}: SyncCardProps) {
  const [entityCount, setEntityCount] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchEntityCount = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get(`/entities/count-by-sync/${syncId}`);
        if (response.ok) {
          const data = await response.json();
          setEntityCount(data.count);
        } else {
          console.error("Failed to fetch entity count:", await response.text());
        }
      } catch (error) {
        console.error("Error fetching entity count:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEntityCount();
  }, [syncId]);

  const getStatusBadge = (status: string) => {
    const statusUpper = status.toUpperCase();
    let variant: "default" | "secondary" | "destructive" = "secondary";

    if (statusUpper === "ACTIVE") variant = "default";
    if (statusUpper === "ERROR") variant = "destructive";

    return (
      <Badge variant={variant} className="text-xs">
        {statusUpper}
      </Badge>
    );
  };

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails();
    } else {
      navigate(`/syncs/${syncId}`);
    }
  };

  const handleChat = () => {
    if (onChat) {
      onChat();
    } else {
      navigate(`/chat?syncId=${syncId}`);
    }
  };

  // Basic search query example for the code block
  const searchCode = `curl -G ${window.location.origin}/search/ \\
 -d sync_id="${syncId}" \\
 -d query="Your search query here"`;

  return (
    <Card className="w-full h-full flex flex-col">
      <div className="p-6 pb-4 flex justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold">{syncName}</h3>
            {getStatusBadge(status)}
          </div>
          <div className="mt-1">
            <code className="text-xs text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded-sm">
              {syncId}
            </code>
          </div>
        </div>
        <div className="w-10 h-10 rounded-full flex items-center justify-center">
          <img
            src={getAppIconUrl(sourceConnectionShortName, resolvedTheme)}
            alt={sourceConnectionShortName}
            className="w-8 h-8"
          />
        </div>
      </div>

      <CardContent className="flex-1 px-6 space-y-4">
        <div className="flex items-center gap-2 text-sm">
          <Database className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">
            {isLoading
              ? "Loading..."
              : entityCount !== null
                ? `${entityCount.toLocaleString()} entities`
                : "No entities"}
          </span>
        </div>

        <CodeBlock
          code={searchCode}
          language="bash"
          badgeText="REST"
          badgeColor="bg-emerald-600 hover:bg-emerald-600"
          title="Search API"
        />
      </CardContent>

      <CardFooter className="flex gap-3 p-6 pt-4">
        <Button onClick={handleViewDetails} variant="outline" className="flex-1">
          View details
        </Button>
        <Button onClick={handleChat} className="flex-1">
          Chat
        </Button>
      </CardFooter>
    </Card>
  );
}
