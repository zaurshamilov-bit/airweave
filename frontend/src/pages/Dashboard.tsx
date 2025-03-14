import { DashboardStats } from "@/components/dashboard/DashboardStats";
import { ConnectedSourcesGrid } from "@/components/dashboard/ConnectedSourcesGrid";
import { ConnectedDestinationsGrid } from "@/components/dashboard/ConnectedDestinationsGrid";
import { ChatCTA } from "@/components/dashboard/ChatCTA";
import { DocsCard } from "@/components/dashboard/DocsCard";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import SyncTableView from "./SyncTableView";

const Dashboard = () => {
  const handleDiscordClick = () => {
    window.open("https://discord.com/invite/484HY9Ehxt", "_blank");
  };

  return (
    <div className="container mx-auto pb-8">
      <div className="space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
            <p className="text-muted-foreground">
              Overview of your data synchronization status
            </p>
          </div>
        </div>

        <DashboardStats />

        <div className="grid gap-8 md:grid-cols-2">
          <ConnectedSourcesGrid />
          <ConnectedDestinationsGrid />
        </div>

        <div className="rounded-lg border pt-4">
          <SyncTableView />
        </div>

        <div className="grid gap-8 md:grid-cols-2">
          <DocsCard />
          <ChatCTA />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
