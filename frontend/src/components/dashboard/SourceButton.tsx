import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";

interface SourceButtonProps {
  id: string;
  name: string;
  shortName: string;
  onClick?: () => void;
}

export const SourceButton = ({ id, name, shortName, onClick }: SourceButtonProps) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

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
    <div className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 md:w-10 md:h-10 overflow-hidden rounded-md flex-shrink-0">
      <img
        src={getAppIconUrl(shortName, resolvedTheme)}
        alt={`${shortName} icon`}
        className="w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 object-contain"
        onError={(e) => {
          // Fallback to initials if icon fails to load
          e.currentTarget.style.display = 'none';
          e.currentTarget.parentElement!.classList.add(getColorClass(shortName));
          e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-xs sm:text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
        }}
      />
    </div>
  );

  return (
    <div
      className={cn(
        "border rounded-lg overflow-hidden cursor-pointer group transition-all min-w-[150px]",
        isDark
          ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900"
          : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50"
      )}
      onClick={onClick}
    >
      <div className="p-2 sm:p-3 md:p-4 flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <SourceIcon />
          <span className="text-xs sm:text-sm font-medium truncate">{name}</span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className={cn(
            "h-6 w-6 sm:h-7 sm:w-7 md:h-8 md:w-8 rounded-full flex-shrink-0",
            isDark
              ? "bg-gray-800/80 text-blue-400 hover:bg-blue-600/20 hover:text-blue-300 group-hover:bg-blue-600/30"
              : "bg-gray-100/80 text-blue-500 hover:bg-blue-100 hover:text-blue-600 group-hover:bg-blue-100/80"
          )}
        >
          <Plus className="h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4 group-hover:h-4 group-hover:w-4 sm:group-hover:h-4.5 sm:group-hover:w-4.5 md:group-hover:h-5 md:group-hover:w-5 transition-all" />
        </Button>
      </div>
    </div>
  );
};

export default SourceButton;
