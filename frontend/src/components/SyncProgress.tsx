import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Clock, MessageSquare } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface SyncStats {
  chunksDetected: number;
  itemsSynced: number;
  itemsToChunk: number;
}

interface SyncSummary {
  deleted: number;
  unchanged: number;
  added: number;
}

export const SyncProgress = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<SyncStats>({
    chunksDetected: 0,
    itemsSynced: 0,
    itemsToChunk: 0,
  });
  const [isComplete, setIsComplete] = useState(false);
  const [summary, setSummary] = useState<SyncSummary>({
    deleted: 8,
    unchanged: 489,
    added: 102,
  });

  useEffect(() => {
    let interval: NodeJS.Timeout;
    const startTime = Date.now();

    const updateProgress = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / 8000, 1); // 8 seconds total

      if (progress >= 1) {
        setIsComplete(true);
        clearInterval(interval);
        return;
      }

      // Simulate increasing chunks detected
      const maxChunks = 1000;
      const currentChunks = Math.floor(maxChunks * (0.5 + progress * 0.5));
      
      // Calculate synced and to-chunk items
      const syncedItems = Math.floor(currentChunks * progress);
      const toChunkItems = currentChunks - syncedItems;

      setStats({
        chunksDetected: currentChunks,
        itemsSynced: syncedItems,
        itemsToChunk: toChunkItems,
      });
    };

    interval = setInterval(updateProgress, 100);
    return () => clearInterval(interval);
  }, []);

  const totalProgress = ((stats.itemsSynced / stats.chunksDetected) * 100) || 0;

  const handleViewSchedule = () => {
    navigate("/sync/schedule");
  };

  const handleTryChat = () => {
    navigate("/chat");
  };

  if (isComplete) {
    return (
      <Card className="w-full max-w-md mx-auto">
        <CardHeader>
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="h-6 w-6 text-green-500" />
            <CardTitle>Sync Complete!</CardTitle>
          </div>
          <CardDescription>
            Successfully processed {stats.chunksDetected.toLocaleString()} items
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="space-y-1">
              <div className="text-2xl font-bold text-green-500">+{summary.added}</div>
              <div className="text-sm text-muted-foreground">Added</div>
            </div>
            <div className="space-y-1">
              <div className="text-2xl font-bold text-yellow-500">{summary.unchanged}</div>
              <div className="text-sm text-muted-foreground">Unchanged</div>
            </div>
            <div className="space-y-1">
              <div className="text-2xl font-bold text-red-500">-{summary.deleted}</div>
              <div className="text-sm text-muted-foreground">Deleted</div>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button onClick={handleTryChat} className="w-full">
            <MessageSquare className="mr-2 h-4 w-4" />
            Try out in chat
          </Button>
          <Button onClick={handleViewSchedule} variant="outline" className="w-full">
            <Clock className="mr-2 h-4 w-4" />
            Schedule Next Sync
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle>Syncing Data</CardTitle>
        <CardDescription>Processing and embedding your data</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progress</span>
            <span>{Math.round(totalProgress)}%</span>
          </div>
          <Progress value={totalProgress} className="h-2" />
        </div>
        
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span>Chunks Detected</span>
            <span>{stats.chunksDetected.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Items Synced</span>
            <span>{stats.itemsSynced.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Items to Process</span>
            <span>{stats.itemsToChunk.toLocaleString()}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
