import { Header } from "@/components/Header";
import { UnifiedDataSourceGrid } from "@/components/data-sources/UnifiedDataSourceGrid";
import { ManageSourceDialog } from "@/components/sources/ManageSourceDialog";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useLocation } from "react-router-dom";

const Sources = () => {
  const location = useLocation();

  // Handle OAuth callback
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const connectedStatus = query.get("connected");

    if (connectedStatus === "success") {
      toast.success("Connection successful", {
        description: "Your data source is now connected."
      });
    } else if (connectedStatus === "error") {
      toast.error("Connection failed", {
        description: "There was an error connecting to your data source."
      });
    }
  }, [location.search]);

  return (
    <div className="container mx-auto pb-8">
      <div className="space-y-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Data Sources</h2>
          <p className="text-muted-foreground">Connect your favorite tools and start syncing data.</p>
        </div>

        <UnifiedDataSourceGrid
          mode="manage"
          renderSourceDialog={(source, options) => (
            <ManageSourceDialog
              open={options.isOpen}
              onOpenChange={options.onOpenChange}
              name={source.name}
              shortName={source.short_name}
              description={source.description || ""}
              onConnect={() => {
                // Use the same direct connection flow as the card
                const sourceObj = {
                  id: source.id,
                  name: source.name,
                  short_name: source.short_name,
                  description: source.description,
                  auth_type: source.auth_type
                };
                // Close the dialog first
                options.onOpenChange(false);
                // Trigger the connection flow directly
                setTimeout(() => {
                  // This will use the same flow as the card's "Add Connection" button
                  document.dispatchEvent(new CustomEvent('initiate-connection', {
                    detail: { source: sourceObj }
                  }));
                }, 100);
              }}
              existingConnections={options.connections}
              isLoading={false}
              labels={source.labels}
            />
          )}
        />
      </div>
    </div>
  );
};

export default Sources;
