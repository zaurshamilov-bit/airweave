import React, { useState } from 'react';
import { toast } from 'sonner';
import { Copy, ArrowRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface SourceAuthenticationViewProps {
  sourceName: string;
  authenticationUrl?: string;
  onRefreshUrl?: () => void;
  isRefreshing?: boolean;
  showBorder?: boolean; // Optional border for collection detail view
}

export const SourceAuthenticationView: React.FC<SourceAuthenticationViewProps> = ({
  sourceName,
  authenticationUrl,
  onRefreshUrl,
  isRefreshing = false,
  showBorder = false
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [copied, setCopied] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const copyToClipboard = () => {
    if (authenticationUrl) {
      navigator.clipboard.writeText(authenticationUrl);
      setCopied(true);
      toast.success('Link copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleConnect = () => {
    if (authenticationUrl) {
      setIsConnecting(true);
      // Small delay for visual feedback before navigation
      setTimeout(() => {
        window.location.href = authenticationUrl;
      }, 100);
    }
  };

  if (!authenticationUrl) {
    // Error state - minimal and helpful
    return (
      <div className={cn(
        "rounded-xl p-6",
        showBorder && "border",
        showBorder && (isDark ? "border-gray-800" : "border-gray-200"),
        isDark ? "bg-gray-900/20" : "bg-gray-50"
      )}>
        <div>
          <p className={cn(
            "text-sm font-medium mb-2",
            isDark ? "text-gray-300" : "text-gray-700"
          )}>
            Unable to generate authentication link
          </p>
          {onRefreshUrl && (
            <button
              onClick={onRefreshUrl}
              disabled={isRefreshing}
              className={cn(
                "inline-flex items-center gap-1.5",
                "px-3 py-1.5 rounded-lg",
                "text-xs font-medium",
                "transition-all",
                isRefreshing
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {isRefreshing ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Refreshing</span>
                </>
              ) : (
                <span>Try again</span>
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "rounded-xl",
      showBorder && "border",
      showBorder && (isDark ? "border-gray-800" : "border-gray-200"),
      isDark ? "bg-gray-900/5" : "bg-gray-50/30"
    )}>
      <div className="space-y-6">
        {/* Header - direct and clear */}
        <div className="flex items-start gap-3">
          <div className={cn(
            "h-2 w-2 rounded-full mt-2 flex-shrink-0",
            "bg-cyan-500"
          )} />
          <div>
            <h3 className={cn(
              "text-base font-semibold mb-1",
              isDark ? "text-white" : "text-gray-900"
            )}>
              Authorize this source connection
            </h3>
            <p className={cn(
              "text-sm",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              Grant permission to Airweave
            </p>
          </div>
        </div>

        {/* Two options with visual hierarchy */}
        <div className="space-y-4">
          {/* Option 1: Share Link */}
          <div className="space-y-2">
            <p className={cn(
              "text-sm font-medium",
              isDark ? "text-gray-200" : "text-gray-800"
            )}>
              Share the secure link
            </p>
            <p className={cn(
              "text-xs",
              isDark ? "text-gray-500" : "text-gray-500"
            )}>
              Send this link to someone who has {sourceName} access
            </p>

            <div className={cn(
              "group relative rounded-lg mt-2",
              "border transition-all duration-200",
              isDark
                ? "bg-black/30 border-white/10 hover:border-white/20"
                : "bg-gray-50 border-gray-200 hover:border-gray-300"
            )}>
              <div className="flex items-center p-2.5">
                <code className={cn(
                  "flex-1 text-xs font-mono",
                  "overflow-x-auto whitespace-nowrap",
                  "scrollbar-none select-all",
                  isDark ? "text-gray-400" : "text-gray-600"
                )}>
                  {authenticationUrl}
                </code>
                <button
                  onClick={copyToClipboard}
                  className={cn(
                    "ml-3 p-1.5 rounded-md flex-shrink-0",
                    "transition-all duration-200",
                    copied
                      ? "bg-green-500/10 text-green-500"
                      : isDark
                        ? "hover:bg-white/5 text-gray-500 hover:text-gray-400"
                        : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                  )}
                  title={copied ? "Copied!" : "Copy link"}
                >
                  <Copy className={cn(
                    "h-3.5 w-3.5",
                    "transition-transform duration-200",
                    copied && "scale-110"
                  )} />
                </button>
              </div>
            </div>
          </div>

          {/* Visual divider with OR */}
          <div className="relative">
            <div className={cn(
              "absolute inset-0 flex items-center"
            )}>
              <div className={cn(
                "w-full border-t",
                isDark ? "border-white/10" : "border-gray-200"
              )} />
            </div>
            <div className="relative flex justify-center">
              <span className={cn(
                "px-3 text-[11px] font-medium uppercase tracking-wider",
                isDark ? "text-gray-600 bg-gray-900" : "text-gray-400 bg-white"
              )}>
                or
              </span>
            </div>
          </div>

          {/* Option 2: Direct Connect */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={cn(
                "text-sm font-medium",
                isDark ? "text-gray-200" : "text-gray-800"
              )}>
                Connect directly
              </p>
              <p className={cn(
                "text-xs mt-0.5",
                isDark ? "text-gray-500" : "text-gray-500"
              )}>
                Use your own {sourceName} account to authorize
              </p>
            </div>

                <button
                  onClick={handleConnect}
                  disabled={isConnecting || !authenticationUrl}
                  className={cn(
                    "inline-flex items-center gap-2",
                    "px-4 py-2 rounded-lg",
                    "text-sm font-medium",
                    "transition-all whitespace-nowrap",

                    isConnecting || !authenticationUrl
                      ? "bg-muted text-muted-foreground cursor-not-allowed"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  )}
                >
                  {isConnecting ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Connecting</span>
                    </>
                  ) : (
                    <>
                      <span>Connect now</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
