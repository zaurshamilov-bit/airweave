import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog";
import { Search, Plus, Calendar } from "lucide-react";

// Mock data for synchronizations
const mockSyncs = [
  {
    id: "sync_1",
    name: "orhanrauf@gmail.com - Slack Sync",
    schedule: "Daily at 2 AM",
    lastRuntime: "2h 15m",
    status: "completed",
    whiteLabelName: "Neena White Label for Slack",
    isWhiteLabel: true
  },
  {
    id: "sync_2",
    name: "lennertjansen@gmail.com - Slack Sync",
    schedule: "Every Monday at 3 AM",
    lastRuntime: "5h 30m",
    status: "completed",
    whiteLabelName: "Neena White Label for Slack",
    isWhiteLabel: true
  },
  {
    id: "sync_3",
    name: "Daily Notion Sync",
    schedule: "Daily at 2 AM",
    lastRuntime: "2h 15m",
    status: "completed",
    whiteLabelName: null,
    isWhiteLabel: false
  },
  {
    id: "sync_4",
    name: "Weekly GitHub Sync",
    schedule: "Every Monday at 3 AM",
    lastRuntime: "5h 30m",
    status: "completed",
    whiteLabelName: null,
    isWhiteLabel: false
  },
];

const SyncSchedule = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);

  const filteredSyncs = mockSyncs.filter(sync => 
    sync.name.toLowerCase().includes(search.toLowerCase()) ||
    sync.schedule.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Synchronizations</h1>
          <p className="text-muted-foreground mt-2">
            View and manage your synchronization history
          </p>
        </div>
        <Dialog open={isScheduleModalOpen} onOpenChange={setIsScheduleModalOpen}>
          <DialogTrigger asChild>
            <Button>
              <Calendar className="mr-2 h-4 w-4" />
              Schedules
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>Synchronization Schedules</DialogTitle>
            </DialogHeader>
            <div className="mt-4">
              <div className="flex justify-between items-center mb-4">
                <Button variant="outline">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Schedule
                </Button>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Frequency</TableHead>
                    <TableHead>Next Run</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>Daily Notion Sync</TableCell>
                    <TableCell>Daily at 2 AM</TableCell>
                    <TableCell>Tomorrow at 2 AM</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">Edit</Button>
                      <Button variant="ghost" size="sm" className="text-destructive">Delete</Button>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="bg-background rounded-lg border">
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search synchronizations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Schedule</TableHead>
              <TableHead>Last Runtime</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>White Label</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredSyncs.map((sync) => (
              <TableRow 
                key={sync.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => navigate(sync.isWhiteLabel ? `/sync/white-label/${sync.id}` : `/sync/${sync.id}`)}
              >
                <TableCell>{sync.name}</TableCell>
                <TableCell>{sync.schedule}</TableCell>
                <TableCell>{sync.lastRuntime}</TableCell>
                <TableCell>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    sync.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                  }`}>
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
    </div>
  );
};

export default SyncSchedule;