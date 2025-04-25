import { useState, useEffect } from "react";
import { DashboardStats } from "@/components/dashboard/DashboardStats";
import { ConnectedSourcesGrid } from "@/components/dashboard/ConnectedSourcesGrid";
import { ConnectedDestinationsGrid } from "@/components/dashboard/ConnectedDestinationsGrid";
import { ChatCTA } from "@/components/dashboard/ChatCTA";
import { DocsCard } from "@/components/dashboard/DocsCard";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";
import { SyncGridView } from "@/components/dashboard";
import { CreateSyncCTA } from "@/components/dashboard/CreateSyncCTA";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";

const Dashboard = () => {
  const [syncs, setSyncs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { resolvedTheme } = useTheme();

  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  useEffect(() => {
    const fetchSyncs = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get("/sync/?limit=1");
        const data = await response.json();
        setSyncs(data);
      } catch (error) {
        console.error("Failed to fetch syncs", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSyncs();
  }, []);

  const handleDiscordClick = () => {
    window.open("https://discord.com/invite/484HY9Ehxt", "_blank");
  };

  if (isLoading) {
    return (
      <div className="container mx-auto pb-8">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
            <p className="text-muted-foreground">
              Overview of your knowledege
            </p>
          </div>
        </div>
        <div className="h-64 flex items-center justify-center">
          <div className="animate-pulse">Loading...</div>
        </div>
      </div>
    );
  }

  if (syncs.length === 0) {
    // Empty state with centered CTA
    return (
      <div className="container mx-auto pb-8">
        <div className="h-[calc(100vh-200px)] flex flex-col items-center justify-center">
          <div className="text-center mb-8">
            <div className="flex flex-row items-center justify-center gap-3 mb-2">
              <h2 className="text-3xl font-bold tracking-tight">Welcome to</h2>
              <img
                src={logoSrc}
                alt="Airweave"
                className="h-10"
              />
            </div>
            <p className="text-muted-foreground">
              Let's get you started.
            </p>
          </div>
          <div className="w-full max-w-3xl">
            <CreateSyncCTA />
          </div>
        </div>
      </div>
    );
  }

  // Regular dashboard content when syncs exist
  return (
    <div className="container mx-auto pb-8">
      <div className="space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Your Syncs</h2>
            <p className="text-muted-foreground">
              Overview of your knowledege
            </p>
          </div>
        </div>

        <SyncGridView />

        <div className="grid gap-8 md:grid-cols-2">
          <DocsCard />
          <ChatCTA />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
