import { cn } from "@/lib/utils";
import { Key, Lock, Rss, Database, Globe } from "lucide-react";

// Mapping of auth types to icons and styling
const AUTH_TYPE_CONFIG: Record<string, { icon: React.ReactNode; className: string }> = {
  "oauth2": {
    icon: <Lock className="h-3 w-3" />,
    className: "bg-blue-950 text-blue-50"
  },
  "api_key": {
    icon: <Key className="h-3 w-3" />,
    className: "bg-amber-950 text-amber-50"
  },
  "basic": {
    icon: <Globe className="h-3 w-3" />,
    className: "bg-purple-950 text-purple-50"
  },
  "odbc": {
    icon: <Database className="h-3 w-3" />,
    className: "bg-green-950 text-green-50"
  },
  "none": {
    icon: <Rss className="h-3 w-3" />,
    className: "bg-gray-800 text-gray-100"
  }
};

export interface AuthTypeBadgeProps {
  authType: string | null;
  className?: string;
}

export function AuthTypeBadge({ authType, className }: AuthTypeBadgeProps) {
  if (!authType) return null;

  // Convert auth type to lowercase for matching
  const authTypeLower = authType.toLowerCase();
  // Find a matching config or use the "api_key" as a fallback
  const config = AUTH_TYPE_CONFIG[authTypeLower] || AUTH_TYPE_CONFIG["api_key"];

  // Format the auth type text (e.g., "api_key" -> "API KEY")
  const formattedAuthType = authType.toUpperCase().replace(/_/g, " ");

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold uppercase",
        config.className,
        className
      )}
    >
      {config.icon}
      <span>{formattedAuthType}</span>
    </div>
  );
}
