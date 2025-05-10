import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

interface SourceButtonProps {
  id: string;
  name: string;
  shortName: string;
  onClick?: () => void;
}

export const SourceButton = ({ id, name, shortName, onClick }: SourceButtonProps) => {
  const { resolvedTheme } = useTheme();

  // Get color class based on shortName
  const getColorClass = (shortName: string) => {
    const colors = [
      "bg-blue-500",
      "bg-green-500",
      "bg-purple-500",
      "bg-orange-500",
      "bg-pink-500",
      "bg-indigo-500",
      "bg-red-500",
      "bg-yellow-500",
    ];

    // Hash the short name to get a consistent color
    const index = shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
    return colors[index];
  };

  // Source icon component
  const SourceIcon = () => (
    <div className="flex items-center justify-center w-10 h-10 overflow-hidden">
      <img
        src={getAppIconUrl(shortName, resolvedTheme)}
        alt={`${shortName} icon`}
        className="w-9 h-9 object-contain"
        onError={(e) => {
          // Fallback to initials if icon fails to load
          e.currentTarget.style.display = 'none';
          e.currentTarget.parentElement!.classList.add(getColorClass(shortName));
          e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
        }}
      />
    </div>
  );

  return (
    <div
      className="border border-border rounded-lg hover:border-border/60 hover:shadow-sm transition-all cursor-pointer overflow-hidden group"
      onClick={onClick}
    >
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SourceIcon />
          <span className="text-sm font-medium">{name}</span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 rounded-full bg-primary/5 hover:bg-primary/10 group-hover:bg-primary/15 group-hover:text-primary transition-all"
        >
          <Plus className="h-4 w-4 group-hover:h-5 group-hover:w-5 transition-all" />
        </Button>
      </div>
    </div>
  );
};

export default SourceButton;
