import { Header } from "@/components/Header";
import { SourcesDataSourceGrid } from "@/components/sources/SourcesDataSourceGrid";

const Sources = () => {
  return (
    <div className="container mx-auto pb-8">
      <div className="space-y-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Data Sources</h2>
          <p className="text-muted-foreground">Connect your favorite tools and start syncing data.</p>
        </div>
        <SourcesDataSourceGrid />
      </div>
    </div>
  );
};

export default Sources;
