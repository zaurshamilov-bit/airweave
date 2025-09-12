import React, { useState } from 'react';
import { toast } from 'sonner';
import { Copy, Info, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface SourceAuthorizationViewProps {
  sourceName: string;
  authenticationUrl?: string;
  onRefreshUrl?: () => void;
  isRefreshing?: boolean;
}

export const SourceAuthorizationView: React.FC<SourceAuthorizationViewProps> = ({
  sourceName,
  authenticationUrl,
  onRefreshUrl,
  isRefreshing = false
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [connectionMethod, setConnectionMethod] = useState<'self' | 'share'>('self');
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    if (authenticationUrl) {
      navigator.clipboard.writeText(authenticationUrl);
      setCopied(true);
      toast.success('Authorization URL copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleConnect = () => {
    if (authenticationUrl) {
      window.location.href = authenticationUrl;
    }
  };

  const handleSendEmail = () => {
    if (authenticationUrl) {
      const subject = encodeURIComponent(`Authenticate ${sourceName}`);
      const body = encodeURIComponent(
        `Hi there,\n\nPlease click the link below to authenticate ${sourceName}:\n\n${authenticationUrl}\n\nThis will allow us to sync your data securely.\n\nThanks!`
      );
      window.open(`mailto:?subject=${subject}&body=${body}`);
    }
  };

  return (
    <div className={cn(
      "p-6 rounded-xl border",
      isDark ? "bg-gray-900/50 border-gray-800" : "bg-white border-gray-200"
    )}>
      <div className="space-y-6">
        {/* Header with status */}
        <div className="flex items-center gap-3">
          <div className={cn(
            "h-2 w-2 rounded-full",
            "bg-cyan-500"
          )} />
          <div>
            <p className={cn(
              "text-sm font-medium",
              isDark ? "text-white" : "text-gray-900"
            )}>
              Connection needs authentication
            </p>
            <p className={cn(
              "text-xs mt-0.5",
              isDark ? "text-gray-500" : "text-gray-500"
            )}>
              Choose how to authenticate access to {sourceName}
            </p>
          </div>
        </div>

        {authenticationUrl ? (
          <>
            {/* Two clean options */}
            <div className="space-y-3">
              {/* Option 1: Connect yourself */}
              <div
                className={cn(
                  "p-5 rounded-xl transition-all cursor-pointer",
                  "border",
                  connectionMethod === 'self'
                    ? isDark
                      ? "border-white/15 bg-white/[0.02]"
                      : "border-gray-300 bg-white"
                    : isDark
                      ? "border-white/10 hover:border-white/15"
                      : "border-gray-200 hover:border-gray-300"
                )}
                onClick={() => setConnectionMethod('self')}
              >
                <h3 className={cn(
                  "text-sm font-semibold mb-1",
                  isDark ? "text-white" : "text-gray-900"
                )}>
                  Connect your own account
                </h3>
                <p className={cn(
                  "text-xs leading-relaxed",
                  isDark ? "text-gray-400" : "text-gray-600"
                )}>
                  Authenticate Airweave to access your {sourceName} data directly. Quick and simple.
                </p>

                {connectionMethod === 'self' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleConnect();
                    }}
                    className={cn(
                      "mt-4 px-4 py-2 rounded-lg",
                      "bg-black hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100",
                      "text-white dark:text-black",
                      "font-medium text-xs",
                      "transition-colors"
                    )}
                  >
                    Authenticate with {sourceName}
                  </button>
                )}
              </div>

              {/* Option 2: Share with someone else */}
              <div
                className={cn(
                  "p-5 rounded-xl transition-all cursor-pointer",
                  "border",
                  connectionMethod === 'share'
                    ? isDark
                      ? "border-white/15 bg-white/[0.02]"
                      : "border-gray-300 bg-white"
                    : isDark
                      ? "border-white/10 hover:border-white/15"
                      : "border-gray-200 hover:border-gray-300"
                )}
                onClick={() => setConnectionMethod('share')}
              >
                <h3 className={cn(
                  "text-sm font-semibold mb-1",
                  isDark ? "text-white" : "text-gray-900"
                )}>
                  Have someone else connect
                </h3>
                <p className={cn(
                  "text-xs leading-relaxed",
                  isDark ? "text-gray-400" : "text-gray-600"
                )}>
                  Send this secure link to someone with {sourceName} access. They'll authenticate on your behalf.
                </p>

                {connectionMethod === 'share' && (
                  <div className="mt-4 space-y-3">
                    {/* Clean URL display */}
                    <div className={cn(
                      "relative",
                      "px-3 py-2 pr-20 rounded-lg",
                      "border",
                      isDark
                        ? "bg-black/30 border-white/10"
                        : "bg-gray-50 border-gray-200"
                    )}>
                      <code className={cn(
                        "block text-[11px] font-mono truncate select-all",
                        isDark ? "text-gray-400" : "text-gray-600"
                      )}>
                        {authenticationUrl}
                      </code>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard();
                        }}
                        className={cn(
                          "absolute right-2 top-1/2 -translate-y-1/2",
                          "px-2.5 py-1 rounded-md",
                          "text-[10px] font-medium",
                          "transition-colors",
                          copied
                            ? isDark
                              ? "text-green-400"
                              : "text-green-600"
                            : isDark
                              ? "text-gray-500 hover:text-gray-300"
                              : "text-gray-500 hover:text-gray-700"
                        )}
                      >
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </div>

                    {/* Email share link */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSendEmail();
                      }}
                      className={cn(
                        "text-xs font-medium transition-colors",
                        isDark
                          ? "text-gray-500 hover:text-gray-300"
                          : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      Share via email
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Help text */}
            <p className={cn(
              "text-[11px]",
              isDark ? "text-gray-600" : "text-gray-400"
            )}>
              This authentication is secure and can be revoked anytime from your {sourceName} settings.
            </p>
          </>
        ) : (
          /* No authentication URL available */
          <div className={cn(
            "p-4 rounded-lg border",
            isDark
              ? "bg-yellow-900/20 border-yellow-800/50"
              : "bg-yellow-50 border-yellow-200"
          )}>
            <div className="flex items-start gap-3">
              <Info className={cn(
                "h-4 w-4 mt-0.5 flex-shrink-0",
                isDark ? "text-yellow-400" : "text-yellow-600"
              )} />
              <div className="flex-1">
                <p className={cn(
                  "text-sm font-medium mb-1",
                  isDark ? "text-yellow-400" : "text-yellow-700"
                )}>
                  Authentication URL not available
                </p>
                <p className={cn(
                  "text-xs",
                  isDark ? "text-yellow-400/80" : "text-yellow-600"
                )}>
                  We're unable to generate an authentication URL at this time. Please try refreshing or contact support if the issue persists.
                </p>
                {onRefreshUrl && (
                  <button
                    onClick={onRefreshUrl}
                    disabled={isRefreshing}
                    className={cn(
                      "mt-3 px-3 py-1.5 rounded-lg text-xs font-medium",
                      "bg-yellow-600 hover:bg-yellow-700 text-white",
                      "transition-colors inline-flex items-center gap-1",
                      "disabled:opacity-50 disabled:cursor-not-allowed"
                    )}
                  >
                    <RefreshCw className={cn(
                      "h-3 w-3",
                      isRefreshing && "animate-spin"
                    )} />
                    {isRefreshing ? "Refreshing..." : "Retry"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
