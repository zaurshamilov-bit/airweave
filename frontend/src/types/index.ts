export interface Connection {
  id: string;
  name: string;
  status: "active" | "inactive" | "error";
  lastSync?: string;
  syncCount?: number;
  documentsCount?: number;
  healthScore?: number;
  createdAt: string;
}

export interface DataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onConnect?: () => void;
  onSelect?: () => void;
  existingConnections?: Connection[];
}