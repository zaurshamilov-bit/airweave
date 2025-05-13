import { cn } from "@/lib/utils";

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
  "PARTIAL ERROR": {
    color: "bg-amber-500",
    textColor: "text-amber-700 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-950/80",
    label: "Partial Error"
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

  // Fallback for unknown statuses
  "default": {
    color: "bg-slate-400",
    textColor: "text-slate-700 dark:text-slate-400",
    bgColor: "bg-slate-50 dark:bg-slate-800/80",
    label: "Unknown"
  }
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge = ({ status, className }: StatusBadgeProps) => {
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

  return (
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
};

export default StatusBadge;
