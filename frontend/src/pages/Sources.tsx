import { Header } from "@/components/Header";
import { UnifiedDataSourceGrid } from "@/components/data-sources/UnifiedDataSourceGrid";
import { ManageSourceDialog } from "@/components/sources/ManageSourceDialog";

const Sources = () => {
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
                console.log(`Connecting to ${source.name}`);
                // Add your connection logic here if needed
              }}
              existingConnections={options.connections}
              isLoading={false}
            />
          )}
        />
      </div>
    </div>
  );
};

export default Sources;
