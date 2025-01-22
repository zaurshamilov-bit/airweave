import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format } from "date-fns";

const mockSyncTableViews = [
  {
    id: "sync_1",
    name: "orhanrauf@gmail.com - Slack Sync",
    schedule: "Daily at 2 AM",
    lastSync: "2024-03-21T02:15:00Z",
    status: "active",
    whiteLabelName: "Neena White Label for Slack"
  },
  {
    id: "sync_2",
    name: "lennertjansen@gmail.com - Slack Sync",
    schedule: "Every Monday at 3 AM",
    lastSync: "2024-03-20T02:12:00Z",
    status: "active",
    whiteLabelName: "Neena White Label for Slack"
  },
  {
    id: "sync_3",
    name: "Daily Notion Sync",
    schedule: "Daily at 2 AM",
    lastSync: "2024-03-21T02:15:00Z",
    status: "paused",
    whiteLabelName: null
  }
];

interface SyncJobsTableProps {
  syncId: string;
}

export const SyncJobsTable = ({ syncId }: SyncJobsTableProps) => {
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-semibold">Active Syncs</h2>
          <p className="text-muted-foreground mt-1">
            Overview of your scheduled synchronizations
          </p>
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="font-semibold text-foreground">Name</TableHead>
            <TableHead className="font-semibold text-foreground">Schedule</TableHead>
            <TableHead className="font-semibold text-foreground">Last Sync</TableHead>
            <TableHead className="font-semibold text-foreground">Status</TableHead>
            <TableHead className="font-semibold text-foreground">White Label</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {mockSyncTableViews.map((sync) => (
            <TableRow key={sync.id} className="cursor-pointer">
              <TableCell className="font-medium">{sync.name}</TableCell>
              <TableCell>{sync.schedule}</TableCell>
              <TableCell>
                {format(new Date(sync.lastSync), "MMM d, yyyy HH:mm")}
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    sync.status === "active"
                      ? "bg-green-100 text-green-800"
                      : "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {sync.status}
                </span>
              </TableCell>
              <TableCell>
                {sync.whiteLabelName ? (
                  <span className="text-sm font-medium text-primary">
                    {sync.whiteLabelName}
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">-</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};