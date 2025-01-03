import { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Database, Plus } from "lucide-react";
import { DestinationManagementDialog } from "@/components/destination/DestinationManagementDialog";
import { AddDestinationWizard } from "@/components/destination/AddDestinationWizard";
import { toast } from "sonner";
import { getDestinationIconUrl } from "@/lib/utils/icons";

interface Destination {
  id: string;
  name: string;
  type: string;
  status: string;
  url: string;
  lastSync: string;
  credentials?: {
    apiKey?: string;
    username?: string;
    password?: string;
  };
  shortName: string;
}

const destinations: Destination[] = [
  {
    id: "1",
    name: "Production Airweave",
    type: "Airweave-Weaviate",
    status: "connected",
    url: "Airweave hosted Weaviate",
    lastSync: "2 hours ago",
    credentials: {
      apiKey: "wv_12345",
    },
    shortName: "airweave",
  },
  {
    id: "2",
    name: "Development Weaviate",
    type: "Weaviate",
    status: "connected",
    url: "https://dev-weaviate.example.com",
    lastSync: "1 day ago",
    credentials: {
      username: "admin",
      password: "secret123",
    },
    shortName: "weaviate",
  },
  {
    id: "3",
    name: "Test Environment",
    type: "Weaviate",
    status: "disconnected",
    url: "https://test-weaviate.example.com",
    lastSync: "Never",
    shortName: "weaviate",
  },
];


const Destinations = () => {
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [isManageOpen, setIsManageOpen] = useState(false);
  const [isAddOpen, setIsAddOpen] = useState(false);

  const handleCardClick = (destination: Destination) => {
    setSelectedDestination(destination);
    setIsManageOpen(true);
  };

  const handleAddComplete = (dbId: string) => {
    // Here you would typically make an API call to create the destination
    toast.success("Database added successfully");
  };

  return (
    <div className="container py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Destinations</h1>
          <p className="text-muted-foreground mt-2">
            Manage your vector database connections
          </p>
        </div>
        <Button onClick={() => setIsAddOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Database
        </Button>
      </div>

      <div className="grid gap-6">
        {destinations.map((destination) => (
          <Card 
            key={destination.id}
            className="cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => handleCardClick(destination)}
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <img 
                    src={getDestinationIconUrl(destination.shortName)} 
                    alt={`${destination.shortName} icon`}
                    className="w-8 h-8"
                  />
                  <div>
                    <CardTitle>{destination.name}</CardTitle>
                    <CardDescription>{destination.type}</CardDescription>
                  </div>
                </div>
                <Badge variant={destination.status === "connected" ? "default" : "secondary"}>
                  {destination.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">URL</span>
                  <span>{destination.url}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Sync</span>
                  <span>{destination.lastSync}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedDestination && (
        <DestinationManagementDialog
          open={isManageOpen}
          onOpenChange={setIsManageOpen}
          destination={selectedDestination}
        />
      )}

      <AddDestinationWizard
        open={isAddOpen}
        onOpenChange={setIsAddOpen}
        onComplete={handleAddComplete}
      />
    </div>
  );
};

export default Destinations;
