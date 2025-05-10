import { Button } from "@/components/ui/button";
import { Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

// Interface for source connections
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

interface CollectionCardProps {
  id: string;
  name: string;
  readableId: string;
  sourceConnections: SourceConnection[];
  onClick?: () => void;
}

export const CollectionCard = ({
  id,
  name,
  readableId,
  sourceConnections = [],
  onClick,
}: CollectionCardProps) => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      navigate(`/collections/${readableId}`);
    }
  };

  const handleViewClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/collections/${readableId}`);
  };

  return (
    <div
      className="relative border border-border hover:border-border/60 rounded-lg hover:shadow-sm transition-all cursor-pointer bg-card text-card-foreground overflow-hidden"
      onClick={handleClick}
    >
      <div className="p-5 pb-20">
        {/* Collection title & URL - large handwritten style */}
        <div>
          <h3 className="text-xl font-medium mb-1" style={{ fontFamily: 'var(--font-sans)' }}>
            {name}
          </h3>
          <p className="text-sm text-muted-foreground">
            {readableId}.airweave.ai
          </p>
        </div>
      </div>

      {/* Source connection icons - bottom right */}
      <div className="absolute bottom-5 right-5">
        <div className="relative" style={{ width: "5rem", height: "2.5rem" }}>
          {sourceConnections.map((connection, index, arr) => (
            <div
              key={connection.id}
              className="absolute w-12 h-12 rounded-md border border-border p-1 flex items-center justify-center overflow-hidden bg-card shadow-sm"
              style={{
                right: `${index * 15}px`,
                zIndex: arr.length - index
              }}
            >
              <img
                src={getAppIconUrl(connection.short_name, resolvedTheme)}
                alt={connection.name}
                className="max-w-full max-h-full w-auto h-auto object-contain"
              />
            </div>
          ))}
        </div>
      </div>

      {/* View & Edit button - left bottom */}
      <div className="absolute bottom-5 left-5">
        <Button
          variant="outline"
          className="h-10 w-32 rounded-md border-border flex items-center justify-center gap-2 hover:bg-accent"
          onClick={handleViewClick}
        >
          <Eye className="h-4 w-4" /> View & edit
        </Button>
      </div>
    </div>
  );
};

export default CollectionCard;
