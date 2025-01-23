export interface Connection {
  id: string;
  name: string;
  integration_type: string;
  status: 'active' | 'error' | 'inactive';
  short_name: string;
  organization_id: string;
  created_by_email: string;
  modified_by_email: string;
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