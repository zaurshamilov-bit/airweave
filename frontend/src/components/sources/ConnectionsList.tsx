import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Connection } from "@/types";
import { Search, Plus, Settings2, Trash2, Play, CheckCircle2, AlertCircle, Database, Clock, FileText, Activity } from "lucide-react";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";

interface ConnectionsListProps {
  connections: Connection[];
  search: string;
  onSearchChange: (value: string) => void;
  onConnect: () => void;
}

export function ConnectionsList({
  connections,
  search,
  onSearchChange,
  onConnect,
}: ConnectionsListProps) {
  const getStatusIcon = (status: Connection['status']) => {
    switch (status) {
      case 'active':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getHealthColor = (score: number) => {
    if (score >= 80) return "bg-green-500";
    if (score >= 50) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search connections..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button onClick={onConnect} className="bg-primary hover:bg-primary/90">
          <Plus className="h-4 w-4 mr-2" />
          Add New
        </Button>
      </div>

      <ScrollArea className="h-[400px] pr-4">
        <div className="grid gap-4">
          {connections.map((connection) => (
            <div
              key={connection.id}
              className="group relative flex flex-col p-4 border rounded-xl bg-card hover:shadow-md transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-primary" />
                    <span className="font-medium">{connection.name}</span>
                    {getStatusIcon(connection.status)}
                  </div>
                  <code className="text-xs px-2 py-0.5 rounded-md bg-muted">
                    {connection.id.substring(0, 12)}
                  </code>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <Play className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <Settings2 className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-2">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="h-4 w-4" />
                    <span>{connection.documentsCount?.toLocaleString() || 0} documents</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Activity className="h-4 w-4" />
                    <span>Used in {connection.syncCount || 0} syncs</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-muted-foreground">Health</span>
                    <span className="text-sm font-medium">{connection.healthScore || 0}%</span>
                  </div>
                  <Progress 
                    value={connection.healthScore || 0} 
                    className={`h-2 ${getHealthColor(connection.healthScore || 0)}`}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t">
                <Badge 
                  variant={
                    connection.status === "active" ? "default" : 
                    connection.status === "error" ? "destructive" : 
                    "secondary"
                  }
                >
                  {connection.status}
                </Badge>
                {connection.lastSync && (
                  <span className="text-xs text-muted-foreground">
                    Last sync: {connection.lastSync}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}