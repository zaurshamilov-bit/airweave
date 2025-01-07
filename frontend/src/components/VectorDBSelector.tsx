import { useEffect, useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Check } from "lucide-react";

import { useToast } from "@/components/ui/use-toast";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/config/api";
import { cn } from "@/lib/utils";

interface Destination {
  id: string;
  name: string;
  description: string | null;
  short_name: string;
  auth_type: string | null;
}

interface ConfigField {
  name: string;
  title: string;
  description: string | null;
  type: string;
}

interface DestinationWithConfig extends Destination {
  config_fields?: {
    fields: ConfigField[];
  };
}

interface Connection {
  id: string;
  name: string;
  status: "active" | "inactive" | "error";
  destination_id: string;
  modified_at: string;
}

interface VectorDBSelectorProps {
  onComplete: (dbId: string) => void;
}

/**
 * Example endpoint for listing existing "destination" connections:
 *   GET /connections/list/destination
 * Returns an array of objects matching the Connection interface above.
 */

export const VectorDBSelector = ({ onComplete }: VectorDBSelectorProps) => {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  // For storing config form states
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configValues, setConfigValues] = useState<Record<string, string>>({
    name: "",
  });
  const [configFields, setConfigFields] = useState<ConfigField[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const { toast } = useToast();

  // Fetch destinations list
  useEffect(() => {
    const fetchDestinations = async () => {
      try {
        const response = await apiClient.get("/destinations/list");
        if (!response.ok) {
          throw new Error("Failed to fetch destinations");
        }
        const data = await response.json();
        // Move weaviate to the top if it exists
        const sortedData = data.sort((a: Destination, b: Destination) => {
          if (a.short_name === "weaviate" && b.short_name !== "weaviate") return -1;
          if (b.short_name === "weaviate" && a.short_name !== "weaviate") return 1;
          return 0;
        });
        setDestinations(sortedData);
      } catch (err) {
        console.error("Error fetching destinations:", err);
        toast({
          variant: "destructive",
          title: "Failed to load vector databases",
          description: "Please try again later",
        });
      }
    };

    fetchDestinations();
  }, [toast]);

  // Fetch existing connections for these destinations
  useEffect(() => {
    const fetchConnections = async () => {
      try {
        const resp = await apiClient.get("/connections/list/destination");
        // It's possible the user doesn't have any connections yet
        if (!resp.ok) {
          if (resp.status === 404) {
            setConnections([]);
            return;
          }
          throw new Error("Failed to fetch destination connections");
        }
        const data = await resp.json();
        setConnections(data);
      } catch (err: any) {
        toast({
          variant: "destructive",
          title: "Failed to load existing connections",
          description: err.message ?? String(err),
        });
      }
    };

    fetchConnections();
  }, [toast]);

  /**
   * When user clicks "Add new connection" or chooses to configure a new one,
   * we fetch config fields for that destination's short_name.
   */
  const handleAddNewConnection = async (dest: Destination) => {
    try {
      const response = await apiClient.get(`/destinations/detail/${dest.short_name}`);
      if (!response.ok) throw new Error("Failed to fetch destination details");
      const data: DestinationWithConfig = await response.json();

      setSelectedDestination(dest);
      setConfigFields(data.config_fields?.fields || []);
      setConfigValues({});
      setShowConfig(true);
    } catch (err) {
      console.error("Error fetching destination details:", err);
      toast({
        variant: "destructive",
        title: "Failed to load configuration",
        description: "Please try again later",
      });
    }
  };

  /**
   * Called when user selects an existing connection from the dropdown.
   * We simply call onComplete with that connection id.
   */
  const handleUseExistingConnection = (connId: string) => {
    onComplete(connId);
  };

  /**
   * Actually connect a new instance for the currently selected destination.
   */
  const handleConnect = async () => {
    if (!selectedDestination) return;

    // Check for required config fields
    const missingFields = configFields.filter((field) => !configValues[field.name]);
    if (missingFields.length > 0) {
      toast({
        variant: "destructive",
        title: "Missing required fields",
        description: `Please fill in: ${missingFields.map((f) => f.title).join(", ")}`,
      });
      return;
    }

    setIsConnecting(true);
    try {
      // Separate name from other config fields
      const { name, ...otherFields } = configValues;

      const requestBody = {
        name: name || `${selectedDestination.name} Connection`, // Use default if empty
        config_fields: otherFields, // All other fields go into config_fields
      };

      const response = await apiClient.post(
        `/connections/connect/destination/${selectedDestination.short_name}`,
        requestBody
      );

      if (!response.ok) throw new Error("Failed to connect");

      const data = await response.json();
      onComplete(data.id);
      setShowConfig(false);
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Connection failed",
        description: "Please check your credentials and try again",
      });
    } finally {
      setIsConnecting(false);
    }
  };

  /**
   * Render the native Weaviate card separately
   */
  const renderNativeWeaviate = () => (
    <Card className="flex flex-col justify-between hover:border-primary/50 transition-colors bg-gradient-to-br from-background to-muted/50">
      <CardHeader>
        <div className="flex items-center space-x-3">
          <img
            src={getDestinationIconUrl("weaviate_native")}
            alt="Weaviate icon"
            className="w-8 h-8"
          />
          <div>
            <CardTitle>Native Weaviate</CardTitle>
            <CardDescription>Built-in vector database</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-grow">
        <p className="text-sm text-muted-foreground">
          Use the built-in Weaviate instance for optimal performance and seamless integration.
        </p>
      </CardContent>
      <CardFooter>
        <Button 
          className="w-full" 
          onClick={() => handleUseExistingConnection("native")}
        >
          Use Native Instance
        </Button>
      </CardFooter>
    </Card>
  );

  /**
   * Group connections by destination type and render them as separate cards
   */
  const renderDestinationGroup = (dest: Destination) => {
    // Skip native Weaviate as it's rendered separately
    if (dest.short_name === "weaviate_native") return null;

    const destConnections = connections
      .filter((c) => c.destination_id === dest.id)
      .sort((a, b) => new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime());

    return (
      <div key={dest.short_name} className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <img
              src={getDestinationIconUrl(dest.short_name)}
              alt={`${dest.name} icon`}
              className="w-6 h-6"
            />
            <h3 className="font-semibold text->lg">{dest.name}</h3>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Existing connections */}
          {destConnections.map((conn) => (
            <Card 
              key={conn.id} 
              className="flex flex-col justify-between hover:border-primary/50 transition-colors bg-muted/5"
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{conn.name}</CardTitle>
                  {conn.status === "active" && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </div>
                <CardDescription>
                  {conn.status === "active" ? "Connected" : "Connection Error"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-grow">
                <p className="text-sm text-muted-foreground">
                  Last modified: {new Date(conn.modified_at).toLocaleDateString()}
                </p>
              </CardContent>
              <CardFooter>
                <Button 
                  className="w-full"
                  variant={conn.status === "active" ? "secondary" : "destructive"}
                  onClick={() => handleUseExistingConnection(conn.id)}
                >
                  {conn.status === "active" ? "Use This Instance" : "Reconnect"}
                </Button>
              </CardFooter>
            </Card>
          ))}
          {/* Always show the "Add New Instance" card first */}
          <Card className="flex flex-col justify-between border-dashed hover:border-primary/50 transition-colors bg-muted/5">
            <CardHeader>
              <CardTitle>New Instance</CardTitle>
              <CardDescription>Configure a new connection</CardDescription>
            </CardHeader>
            <CardContent className="flex-grow">
              <p className="text-sm text-muted-foreground">
                Add another {dest.name} instance to your vector database collection.
              </p>
            </CardContent>
            <CardFooter>
              <Button 
                variant="secondary"
                className="w-full" 
                onClick={() => handleAddNewConnection(dest)}
              >
                Add New Instance
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    );
  };

  // If we are showing config form, show that in a single card
  if (showConfig && selectedDestination) {
    return (
      <div className="max-w-md mx-auto">
        <Card>
          <CardHeader>
            <div className="flex items-center space-x-4">
              <img
                src={getDestinationIconUrl(selectedDestination.short_name)}
                alt={`${selectedDestination.name} icon`}
                className="w-8 h-8"
              />
              <div>
                <CardTitle>{selectedDestination.name}</CardTitle>
                <CardDescription>Configure your connection</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Name
                <span className="text-xs text-muted-foreground ml-2">
                  (Optional name for this connection)
                </span>
              </label>
              <Input
                type="text"
                value={configValues.name || ""}
                onChange={(e) =>
                  setConfigValues((prev) => ({
                    ...prev,
                    name: e.target.value,
                  }))
                }
                placeholder={`${selectedDestination.name} Connection`}
              />
            </div>
            
            {configFields.map((field) => (
              <div key={field.name} className="space-y-2">
                <label className="text-sm font-medium">
                  {field.title}
                  {field.description && (
                    <span className="text-xs text-muted-foreground ml-2">
                      ({field.description})
                    </span>
                  )}
                </label>
                <Input
                  type={field.type === "string" ? "text" : field.type}
                  value={configValues[field.name] || ""}
                  onChange={(e) =>
                    setConfigValues((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                  placeholder={`Enter ${field.title.toLowerCase()}`}
                />
              </div>
            ))}
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => {
                setShowConfig(false);
                setSelectedDestination(null);
              }}
            >
              Back
            </Button>
            <Button onClick={handleConnect} disabled={isConnecting}>
              {isConnecting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Connecting
                </>
              ) : (
                "Connect"
              )}
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Native Weaviate always on top */}
      <div className="max-w-md">
        {renderNativeWeaviate()}
      </div>

      {/* Other destinations */}
      <div className="space-y-8">
        {destinations
          .filter(dest => dest.short_name !== "weaviate_native")
          .sort((a, b) => a.name.localeCompare(b.name))
          .map(renderDestinationGroup)}
      </div>
    </div>
  );
};