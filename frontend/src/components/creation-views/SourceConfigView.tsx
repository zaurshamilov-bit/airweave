import React, { useState, useEffect } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Copy, ExternalLink, Check, User, Users, Mail, Link2, ChevronRight, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface SourceConfigViewProps {
  humanReadableId: string;
  isAddingToExisting?: boolean;
}

export const SourceConfigView: React.FC<SourceConfigViewProps> = ({ humanReadableId, isAddingToExisting = false }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const {
    collectionId,
    collectionName,
    selectedSource,
    sourceName,
    authMode,
    setAuthMode,
    setOAuthData,
    setConnectionId,
    setStep,
  } = useCollectionCreationStore();

  const [isCreating, setIsCreating] = useState(false);
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [configData, setConfigData] = useState<Record<string, string>>({});
  const [useOwnCredentials, setUseOwnCredentials] = useState(false);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [connectionUrl, setConnectionUrl] = useState('');
  const [connectionMethod, setConnectionMethod] = useState<'self' | 'share'>('share'); // Default to share
  const [copied, setCopied] = useState(false);

  // Fetch source details to understand config requirements
  useEffect(() => {
    const fetchSourceDetails = async () => {
      if (!selectedSource) return;

      try {
        const response = await apiClient.get(`/sources/detail/${selectedSource}`);
        if (response.ok) {
          const source = await response.json();
          // Set auth mode based on source auth type
          if (source.auth_type?.startsWith('oauth2')) {
            setAuthMode('oauth2');
          } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
            setAuthMode('direct_auth');
          }
        }
      } catch (error) {
        console.error('Error fetching source details:', error);
      }
    };

    fetchSourceDetails();
  }, [selectedSource, setAuthMode]);

  const handleCreate = async () => {
    setIsCreating(true);

    try {
      const payload: any = {
        name: `${sourceName} - ${collectionName}`,
        description: `${sourceName} connection for ${collectionName}`,
        short_name: selectedSource,
        collection: collectionId,
        auth_mode: authMode || 'oauth2',
        sync_immediately: false,
      };

      // Add config fields if any
      if (Object.keys(configData).length > 0) {
        payload.config_fields = configData;
      }

      // Handle different auth modes
      if (authMode === 'direct_auth') {
        if (Object.keys(authFields).length === 0) {
          toast.error('Please provide authentication credentials');
          setIsCreating(false);
          return;
        }
        payload.auth_fields = authFields;
      } else if (authMode === 'oauth2' || !authMode) {
        if (useOwnCredentials) {
          if (!clientId || !clientSecret) {
            toast.error('Please provide OAuth client credentials');
            setIsCreating(false);
            return;
          }
          payload.client_id = clientId;
          payload.client_secret = clientSecret;
        }
        payload.redirect_url = `${window.location.origin}?oauth_return=true`;
      }

      const response = await apiClient.post('/source-connections', payload);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create connection');
      }

      const result = await response.json();

      // Check if OAuth flow is needed
      if (result.authentication_url) {
        setOAuthData(
          result.id,
          payload.redirect_url || `${window.location.origin}?oauth_return=true`,
          result.authentication_url
        );

        setConnectionUrl(result.authentication_url);
        toast.success('Connection ready');
      } else {
        // Direct auth successful
        setConnectionId(result.id);
        setStep('success');
      }

    } catch (error) {
      console.error('Error creating source connection:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create connection');
    } finally {
      setIsCreating(false);
    }
  };

  const copyToClipboard = () => {
    if (connectionUrl) {
      navigator.clipboard.writeText(connectionUrl);
      setCopied(true);
      toast.success('Copied');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleConnect = () => {
    if (connectionUrl) {
      window.location.href = connectionUrl;
    }
  };

  const handleSendEmail = () => {
    if (connectionUrl) {
      const subject = encodeURIComponent(`Connect your ${sourceName} to ${collectionName}`);
      const body = encodeURIComponent(
        `Hi there,\n\nPlease click the link below to connect your ${sourceName} account:\n\n${connectionUrl}\n\nThis will allow us to sync your data securely.\n\nThanks!`
      );
      window.open(`mailto:?subject=${subject}&body=${body}`);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-8 py-10 flex-1 overflow-auto">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Create Source Connection
            </h2>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              {sourceName} Connection
            </p>
          </div>

          {/* Connection created state - Ultra sleek design */}
          {connectionUrl ? (
            <div className="space-y-6">
              {/* Sleek tab toggle */}
              <div className="flex gap-6 border-b border-gray-200 dark:border-gray-800">
                <button
                  onClick={() => setConnectionMethod('share')}
                  className={cn(
                    "pb-3 text-sm font-medium transition-all relative",
                    connectionMethod === 'share'
                      ? "text-gray-900 dark:text-white"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                  )}
                >
                  Share with user
                  {connectionMethod === 'share' && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
                  )}
                </button>
                <button
                  onClick={() => setConnectionMethod('self')}
                  className={cn(
                    "pb-3 text-sm font-medium transition-all relative",
                    connectionMethod === 'self'
                      ? "text-gray-900 dark:text-white"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                  )}
                >
                  Connect yourself
                </button>
              </div>

              {/* Dynamic content based on selection */}
              <div className="space-y-4">
                {connectionMethod === 'share' ? (
                  <>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Share this secure link
                    </p>

                    {/* Clean URL display with integrated copy button */}
                    <div className={cn(
                      "relative flex items-center gap-3 px-4 py-3 pr-12 rounded-lg",
                      "border transition-all",
                      "font-mono text-xs",
                      isDark
                        ? "bg-gray-900/50 border-gray-800"
                        : "bg-gray-50 border-gray-200"
                    )}>
                      <Link2 className="h-3.5 w-3.5 flex-shrink-0 opacity-50" />
                      <span className={cn(
                        "flex-1 truncate",
                        isDark ? "text-gray-400" : "text-gray-600"
                      )}>
                        {connectionUrl}
                      </span>
                      <button
                        onClick={copyToClipboard}
                        className={cn(
                          "absolute right-2 p-2 rounded transition-all",
                          copied
                            ? "bg-green-600/10 text-green-500"
                            : isDark
                              ? "hover:bg-gray-800 text-gray-500 hover:text-gray-300"
                              : "hover:bg-gray-200 text-gray-400 hover:text-gray-600"
                        )}
                        title="Copy link"
                      >
                        {copied ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>

                    {/* Quick actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          window.open(`https://slack.com/share?url=${encodeURIComponent(connectionUrl)}`, '_blank');
                        }}
                        className={cn(
                          "flex-1 px-4 py-2.5 text-sm rounded-lg",
                          "border transition-all duration-200",
                          "hover:scale-[1.02]",
                          isDark
                            ? "border-gray-800 hover:bg-gray-800 text-gray-400 hover:text-gray-200"
                            : "border-gray-200 hover:bg-gray-50 text-gray-600 hover:text-gray-900"
                        )}
                      >
                        Share on Slack
                      </button>
                      <button
                        onClick={() => {
                          window.open(`https://teams.microsoft.com/share?url=${encodeURIComponent(connectionUrl)}`, '_blank');
                        }}
                        className={cn(
                          "flex-1 px-4 py-2.5 text-sm rounded-lg",
                          "border transition-all duration-200",
                          "hover:scale-[1.02]",
                          isDark
                            ? "border-gray-800 hover:bg-gray-800 text-gray-400 hover:text-gray-200"
                            : "border-gray-200 hover:bg-gray-50 text-gray-600 hover:text-gray-900"
                        )}
                      >
                        Share on Teams
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Authenticate with your {sourceName} account
                    </p>
                    <button
                      onClick={handleConnect}
                      className={cn(
                        "w-full py-4 px-6 rounded-xl",
                        "bg-gradient-to-r from-blue-600 to-blue-500",
                        "hover:from-blue-700 hover:to-blue-600",
                        "text-white font-medium",
                        "transition-all duration-300 transform hover:scale-[1.02]",
                        "shadow-lg hover:shadow-xl",
                        "flex items-center justify-center gap-3",
                        "relative overflow-hidden group"
                      )}
                    >
                      <span className="relative z-10">Connect Now</span>
                      <ChevronRight className="h-4 w-4 relative z-10 transition-transform group-hover:translate-x-1" />
                      <div className="absolute inset-0 bg-gradient-to-r from-blue-700 to-blue-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <>
              {/* Form fields - Clean minimal design */}
              <div className="space-y-6">
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                    Name
                  </label>
                  <input
                    type="text"
                    value={`${sourceName} Connection`}
                    disabled
                    className={cn(
                      "w-full px-4 py-2.5 rounded-lg text-sm",
                      "border bg-transparent",
                      isDark
                        ? "border-gray-800 text-gray-400"
                        : "border-gray-200 text-gray-500"
                    )}
                  />
                </div>

                {/* Auth config fields */}
                {authMode === 'direct_auth' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      Authentication
                    </label>
                    <input
                      type="password"
                      placeholder="API Key or Access Token"
                      value={authFields.api_key || ''}
                      onChange={(e) => setAuthFields({ api_key: e.target.value })}
                      className={cn(
                        "w-full px-4 py-2.5 rounded-lg text-sm",
                        "border bg-transparent",
                        "focus:outline-none focus:ring-1 focus:ring-blue-500",
                        isDark
                          ? "border-gray-800 text-white placeholder:text-gray-600"
                          : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                      )}
                    />
                  </div>
                )}

                {/* Config fields */}
                {selectedSource && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      Configuration (optional)
                    </label>
                    <input
                      type="text"
                      placeholder="Additional settings"
                      className={cn(
                        "w-full px-4 py-2.5 rounded-lg text-sm",
                        "border bg-transparent",
                        "focus:outline-none focus:ring-1 focus:ring-blue-500",
                        isDark
                          ? "border-gray-800 text-white placeholder:text-gray-600"
                          : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                      )}
                    />
                  </div>
                )}

                {/* OAuth option - Sleek toggle */}
                {authMode === 'oauth2' && (
                  <div>
                    <label className="flex items-center gap-3 cursor-pointer group">
                      <div className="relative">
                        <input
                          type="checkbox"
                          checked={useOwnCredentials}
                          onChange={(e) => setUseOwnCredentials(e.target.checked)}
                          className="sr-only"
                        />
                        <div className={cn(
                          "w-10 h-6 rounded-full transition-colors",
                          useOwnCredentials
                            ? "bg-blue-600"
                            : isDark ? "bg-gray-800" : "bg-gray-200"
                        )}>
                          <div className={cn(
                            "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform",
                            useOwnCredentials && "translate-x-4"
                          )} />
                        </div>
                      </div>
                      <span className="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200">
                        Use custom OAuth credentials
                      </span>
                    </label>

                    {useOwnCredentials && (
                      <div className="mt-4 space-y-3 pl-13">
                        <input
                          type="text"
                          placeholder="Client ID"
                          value={clientId}
                          onChange={(e) => setClientId(e.target.value)}
                          className={cn(
                            "w-full px-3 py-2 rounded-lg text-sm",
                            "border bg-transparent",
                            "focus:outline-none focus:ring-1 focus:ring-blue-500",
                            isDark
                              ? "border-gray-800 text-white placeholder:text-gray-600"
                              : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                        <input
                          type="password"
                          placeholder="Client Secret"
                          value={clientSecret}
                          onChange={(e) => setClientSecret(e.target.value)}
                          className={cn(
                            "w-full px-3 py-2 rounded-lg text-sm",
                            "border bg-transparent",
                            "focus:outline-none focus:ring-1 focus:ring-blue-500",
                            isDark
                              ? "border-gray-800 text-white placeholder:text-gray-600"
                              : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Bottom actions - Clean minimal */}
      <div className={cn(
        "px-8 py-6 border-t",
        isDark ? "border-gray-800" : "border-gray-200"
      )}>
        <div className="flex gap-3">
          <button
            onClick={() => setStep('source-select')}
            className={cn(
              "px-6 py-2.5 rounded-lg text-sm font-medium transition-colors",
              isDark
                ? "text-gray-400 hover:text-gray-200"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            Back
          </button>

          {!connectionUrl && (
            <button
              onClick={handleCreate}
              disabled={isCreating}
              className={cn(
                "flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "bg-blue-600 hover:bg-blue-700 text-white"
              )}
            >
              {isCreating ? 'Creating...' : 'Create'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
