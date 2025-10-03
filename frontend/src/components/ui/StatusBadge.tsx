import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// Status config based on backend shared_models.py status definitions
export const statusConfig = {
  // Collection statuses
  "ACTIVE": {
    color: "bg-emerald-500",
    textColor: "text-emerald-700 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-950/80",
    label: "Active"
  },
  "active": {
    color: "bg-emerald-500",
    textColor: "text-emerald-700 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-950/80",
    label: "Active"
  },
  "ERROR": {
    color: "bg-rose-500",
    textColor: "text-rose-700 dark:text-rose-400",
    bgColor: "bg-rose-50 dark:bg-rose-950/80",
    label: "Error"
  },
  "error": {
    color: "bg-rose-500",
    textColor: "text-rose-700 dark:text-rose-400",
    bgColor: "bg-rose-50 dark:bg-rose-950/80",
    label: "Error"
  },
  "NEEDS SOURCE": {
    color: "bg-slate-400",
    textColor: "text-slate-700 dark:text-slate-400",
    bgColor: "bg-slate-50 dark:bg-slate-800/80",
    label: "Needs Source"
  },
  "needs source": {
    color: "bg-slate-400",
    textColor: "text-slate-700 dark:text-slate-400",
    bgColor: "bg-slate-50 dark:bg-slate-800/80",
    label: "Needs Source"
  },

  // Source connection statuses
  "IN_PROGRESS": {
    color: "bg-blue-500",
    textColor: "text-blue-700 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950/80",
    label: "Syncing"
  },
  "in_progress": {
    color: "bg-blue-500",
    textColor: "text-blue-700 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950/80",
    label: "In Progress"
  },
  "failing": {
    color: "bg-rose-500",
    textColor: "text-rose-700 dark:text-rose-400",
    bgColor: "bg-rose-50 dark:bg-rose-950/80",
    label: "Failing"
  },

  // Sync job statuses
  "pending": {
    color: "bg-amber-500",
    textColor: "text-amber-700 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-950/80",
    label: "Pending"
  },
  "completed": {
    color: "bg-emerald-500",
    textColor: "text-emerald-700 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-950/80",
    label: "Completed"
  },
  "failed": {
    color: "bg-rose-500",
    textColor: "text-rose-700 dark:text-rose-400",
    bgColor: "bg-rose-50 dark:bg-rose-950/80",
    label: "Failed"
  },
  "cancelled": {
    color: "bg-rose-500",
    textColor: "text-rose-700 dark:text-rose-400",
    bgColor: "bg-rose-50 dark:bg-rose-950/80",
    label: "Cancelled"
  },

  // Fallback for unknown statuses
  "default": {
    color: "bg-slate-400",
    textColor: "text-slate-700 dark:text-slate-400",
    bgColor: "bg-slate-50 dark:bg-slate-800/80",
    label: "Unknown"
  }
};

// Status descriptions for tooltips
const getStatusDescription = (statusKey: string): string | null => {
  const normalizedKey = statusKey.toUpperCase();

  const descriptions: Record<string, string> = {
    "ACTIVE": "At least one source connection has completed a sync or is currently syncing. Your collection has data and is ready for queries.",
    "ERROR": "All source connections have failed their last sync. Check your connections and authentication to resolve sync issues.",
    "NEEDS SOURCE": "This collection has no authenticated connections, or connections exist but haven't successfully synced yet. Configure a source or wait for the initial sync to complete."
  };

  return descriptions[normalizedKey] || null;
};

interface StatusBadgeProps {
  status: string;
  className?: string;
  showTooltip?: boolean;
}

export const StatusBadge = ({ status, className, showTooltip = true }: StatusBadgeProps) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Get status configuration or default
  const getStatusConfig = (statusKey: string = "") => {
    // Try exact match first
    if (statusKey in statusConfig) {
      return statusConfig[statusKey as keyof typeof statusConfig];
    }

    // Try case-insensitive match
    const lowerKey = statusKey.toLowerCase();
    for (const key in statusConfig) {
      if (key.toLowerCase() === lowerKey) {
        return statusConfig[key as keyof typeof statusConfig];
      }
    }

    // Return default if no match
    const formatted = statusKey ? statusKey.charAt(0).toUpperCase() + statusKey.slice(1).toLowerCase() : "Unknown";
    return {
      ...statusConfig["default"],
      label: formatted
    };
  };

  const config = getStatusConfig(status);
  const description = getStatusDescription(status);

  const badge = (
    <div className={cn(
      "inline-flex items-center gap-1.5 py-1 px-2.5 rounded-full",
      config.bgColor,
      className
    )}>
      <div className={cn("h-2 w-2 rounded-full", config.color)}></div>
      <span className={cn("text-xs font-medium", config.textColor)}>
        {config.label}
      </span>
    </div>
  );

  // If no tooltip should be shown or no description exists, return badge directly
  if (!showTooltip || !description) {
    return badge;
  }

  // Return badge with tooltip
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="inline-flex cursor-help">
            {badge}
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className={cn(
            "max-w-sm p-4 border shadow-lg",
            isDark
              ? "bg-gray-900 border-gray-700 text-gray-100"
              : "bg-white border-gray-200 text-gray-900"
          )}
        >
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className={cn("h-2.5 w-2.5 rounded-full", config.color)}></div>
              <span className="text-sm font-semibold">
                {config.label}
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {description}
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default StatusBadge;
