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
      <div className="p-3 sm:p-4 md:p-5 pb-16 sm:pb-18 md:pb-20">
        {/* Collection title & URL - large handwritten style */}
        <div>
          <h3 className="text-base sm:text-lg md:text-xl font-medium mb-1" style={{ fontFamily: 'var(--font-sans)' }}>
            {name}
          </h3>
          <p className="text-xs sm:text-sm text-muted-foreground truncate">
            {readableId}.airweave.ai
          </p>
        </div>
      </div>

      {/* Source connection icons - bottom right */}
      <div className="absolute bottom-3 sm:bottom-4 md:bottom-5 right-3 sm:right-4 md:right-5">
        <div className="relative" style={{ width: "4rem", height: "2.5rem" }}>
          {sourceConnections.map((connection, index, arr) => (
            <div
              key={connection.id}
              className="absolute w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-md border border-border p-1 flex items-center justify-center overflow-hidden bg-card shadow-sm"
              style={{
                right: `${index * 12}px`,
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
      <div className="absolute bottom-3 sm:bottom-4 md:bottom-5 left-3 sm:left-4 md:left-5">
        <Button
          variant="outline"
          className="h-8 sm:h-9 md:h-10 w-24 sm:w-28 md:w-32 rounded-md border-border flex items-center justify-center gap-1 sm:gap-2 hover:bg-accent text-xs sm:text-sm"
          onClick={handleViewClick}
        >
          <Eye className="h-3 w-3 sm:h-4 sm:w-4" /> View & edit
        </Button>
      </div>
    </div>
  );
};

export default CollectionCard;
