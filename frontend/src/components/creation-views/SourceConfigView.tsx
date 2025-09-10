import React, { useState, useEffect } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Copy, ExternalLink, Check, User, Users, Mail, Link2, ChevronRight, Send, Info, HelpCircle, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface SourceConfigViewProps {
  humanReadableId: string;
  isAddingToExisting?: boolean;
}

interface SourceDetails {
  short_name: string;
  name: string;
  auth_type?: string;
  auth_config_class?: string;
  auth_fields?: {
    fields: Array<{
      name: string;
      title?: string;
      description?: string;
      type?: string;
      required?: boolean;
    }>;
  };
  config_fields?: {
    fields: Array<{
      name: string;
      title?: string;
      description?: string;
      type?: string;
      required?: boolean;
    }>;
  };
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
    handleBackFromSourceConfig,
    setSourceConnectionName,
  } = useCollectionCreationStore();

  const [isCreating, setIsCreating] = useState(false);
  const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [configData, setConfigData] = useState<Record<string, string>>({});
  const [useOwnCredentials, setUseOwnCredentials] = useState(false);
  const [connectionName, setConnectionName] = useState(`${sourceName} Connection`);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  // Sync connection name with store on mount and when it changes
  useEffect(() => {
    setSourceConnectionName(connectionName);
  }, []);
  const [connectionUrl, setConnectionUrl] = useState('');
  const [connectionMethod, setConnectionMethod] = useState<'self' | 'share'>('share'); // Default to share
  const [copied, setCopied] = useState(false);

  // Sources that require custom OAuth credentials (BYOC - Bring Your Own Credentials)
  const BYOC_SOURCES = ['google_drive', 'gmail', 'dropbox', 'google_calendar'];

  // Check if source requires custom OAuth credentials
  const requiresCustomOAuth = () => {
    return BYOC_SOURCES.includes(selectedSource || '') ||
           sourceDetails?.auth_config_class?.includes('BYOC');
  };

  // Check if this is a config-based auth source (like GitHub)
  const isConfigAuth = () => {
    return sourceDetails?.auth_type === 'config_class' &&
           !sourceDetails?.auth_config_class?.includes('OAuth');
  };

  // Fetch source details to understand config requirements
  useEffect(() => {
    const fetchSourceDetails = async () => {
      if (!selectedSource) return;

      try {
        const response = await apiClient.get(`/sources/detail/${selectedSource}`);
        if (response.ok) {
          const source = await response.json();
          setSourceDetails(source);

          // Set auth mode based on source auth type
          if (source.auth_type === 'config_class') {
            // Check if it's OAuth config or direct config
            if (source.auth_config_class?.includes('OAuth')) {
              setAuthMode('oauth2');
              // Auto-enable custom credentials for BYOC sources
              const isBYOC = BYOC_SOURCES.includes(selectedSource || '') ||
                            source.auth_config_class?.includes('BYOC');
              if (isBYOC) {
                setUseOwnCredentials(true);
              }
            } else {
              setAuthMode('config_auth');
            }
          } else if (source.auth_type?.startsWith('oauth2')) {
            setAuthMode('oauth2');
          } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
            setAuthMode('direct_auth');
          }

          // Initialize auth fields for config-based auth
          if (source.auth_fields?.fields) {
            const initialValues: Record<string, string> = {};
            source.auth_fields.fields.forEach((field: any) => {
              // Skip token fields that come from OAuth
              if (!field.name.includes('token') && !field.name.includes('client_')) {
                initialValues[field.name] = '';
              }
            });
            setAuthFields(initialValues);
          }

          // Initialize config fields
          if (source.config_fields?.fields) {
            const initialValues: Record<string, string> = {};
            source.config_fields.fields.forEach((field: any) => {
              initialValues[field.name] = '';
            });
            setConfigData(initialValues);
          }
        }
      } catch (error) {
        console.error('Error fetching source details:', error);
      }
    };

    fetchSourceDetails();
  }, [selectedSource, setAuthMode]);

  // Update connection name when source name changes
  useEffect(() => {
    setConnectionName(`${sourceName} Connection`);
  }, [sourceName]);

  const handleCreate = async () => {
    setIsCreating(true);

    try {
      const payload: any = {
        name: connectionName.trim() || `${sourceName} Connection`,
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
      if (authMode === 'config_auth') {
        // Config-based auth (like GitHub)
        if (Object.keys(authFields).length === 0) {
          toast.error('Please provide all required configuration fields');
          setIsCreating(false);
          return;
        }
        payload.auth_fields = authFields;
      } else if (authMode === 'direct_auth') {
        // Direct auth (API key, basic auth)
        if (Object.keys(authFields).length === 0) {
          toast.error('Please provide authentication credentials');
          setIsCreating(false);
          return;
        }
        payload.auth_fields = authFields;
      } else if (authMode === 'oauth2' || !authMode) {
        // OAuth2 flow
        if (requiresCustomOAuth() || useOwnCredentials) {
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
        // Direct auth or config auth successful
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
            <input
              type="text"
              value={connectionName}
              onChange={(e) => {
                setConnectionName(e.target.value);
                setSourceConnectionName(e.target.value);
              }}
              placeholder="Connection name"
              className={cn(
                "mt-2 text-sm bg-transparent border-none outline-none",
                "text-gray-500 dark:text-gray-400",
                "hover:text-gray-700 dark:hover:text-gray-300",
                "focus:text-gray-900 dark:focus:text-white",
                "transition-colors cursor-text",
                "px-0 py-0 w-full"
              )}
              style={{ minWidth: '200px' }}
            />
          </div>

          {/* Connection created state - Minimal clean design */}
          {connectionUrl ? (
            <div className="space-y-6">
              {/* Success indicator */}
              <div className="flex items-center gap-2">
                <div className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  isDark ? "bg-green-500" : "bg-green-600"
                )} />
                <div>
                  <p className={cn(
                    "text-sm font-medium",
                    isDark ? "text-white" : "text-gray-900"
                  )}>
                    Connection ready
                  </p>
                  <p className={cn(
                    "text-xs mt-0.5",
                    isDark ? "text-gray-500" : "text-gray-500"
                  )}>
                    Choose how to authorize access to {sourceName}
                  </p>
                </div>
              </div>

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
                    Authorize Airweave to access your {sourceName} data directly. Quick and simple.
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
                      Authorize with {sourceName}
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
                    Send this secure link to someone with {sourceName} access. They'll authorize on your behalf.
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
                          {connectionUrl}
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
                This authorization is secure and can be revoked anytime from your {sourceName} settings.
              </p>
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
                    value={connectionName}
                    onChange={(e) => setConnectionName(e.target.value)}
                    placeholder="Enter connection name"
                    className={cn(
                      "w-full px-4 py-2.5 rounded-lg text-sm",
                      "border transition-colors",
                      "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                      isDark
                        ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                        : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                    )}
                  />
                </div>

                {/* Config-based auth fields (like GitHub) */}
                {authMode === 'config_auth' && sourceDetails?.auth_fields?.fields && (
                  <div className="space-y-4">
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Configuration
                    </label>
                    {sourceDetails.auth_fields.fields.map((field) => (
                      <div key={field.name}>
                        <label className="block text-sm font-medium mb-1.5">
                          {field.title || field.name}
                          {field.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        {field.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                            {field.description}
                          </p>
                        )}
                        <input
                          type={field.name.includes('password') || field.name.includes('token') ? 'password' : 'text'}
                          placeholder={field.description || `Enter ${field.title || field.name}`}
                          value={authFields[field.name] || ''}
                          onChange={(e) => setAuthFields({ ...authFields, [field.name]: e.target.value })}
                          className={cn(
                            "w-full px-4 py-2.5 rounded-lg text-sm",
                            "border bg-transparent",
                            "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                            isDark
                              ? "border-gray-800 text-white placeholder:text-gray-600"
                              : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Direct auth fields (API key, basic auth) */}
                {authMode === 'direct_auth' && sourceDetails?.auth_fields?.fields && (
                  <div className="space-y-4">
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Authentication
                    </label>
                    {sourceDetails.auth_fields.fields.map((field) => (
                      <div key={field.name}>
                        <label className="block text-sm font-medium mb-1.5">
                          {field.title || field.name}
                          {field.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        <input
                          type={field.name.includes('password') || field.name.includes('key') || field.name.includes('token') ? 'password' : 'text'}
                          placeholder={field.description || `Enter ${field.title || field.name}`}
                          value={authFields[field.name] || ''}
                          onChange={(e) => setAuthFields({ ...authFields, [field.name]: e.target.value })}
                          className={cn(
                            "w-full px-4 py-2.5 rounded-lg text-sm",
                            "border bg-transparent",
                            "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                            isDark
                              ? "border-gray-800 text-white placeholder:text-gray-600"
                              : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Config fields (optional additional configuration) */}
                {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 && (
                  <div className="space-y-4">
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Additional Configuration (optional)
                    </label>
                    {sourceDetails.config_fields.fields.map((field) => (
                      <div key={field.name}>
                        <label className="block text-sm font-medium mb-1.5">
                          {field.title || field.name}
                        </label>
                        {field.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                            {field.description}
                          </p>
                        )}
                        <input
                          type="text"
                          placeholder={field.description || `Enter ${field.title || field.name}`}
                          value={configData[field.name] || ''}
                          onChange={(e) => setConfigData({ ...configData, [field.name]: e.target.value })}
                          className={cn(
                            "w-full px-4 py-2.5 rounded-lg text-sm",
                            "border bg-transparent",
                            "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                            isDark
                              ? "border-gray-800 text-white placeholder:text-gray-600"
                              : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* OAuth option - Sleek toggle or always on for BYOC sources */}
                {authMode === 'oauth2' && (
                  <div>
                    {requiresCustomOAuth() ? (
                      // For BYOC sources, show info and fields directly
                      <div className="space-y-4">
                        <div className={cn(
                          "flex items-start gap-2 p-3 rounded-lg",
                          isDark ? "bg-blue-900/20 text-blue-400" : "bg-blue-50 text-blue-600"
                        )}>
                          <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                          <p className="text-sm">
                            {sourceName} requires you to provide your own OAuth application credentials.
                            You'll need to create an OAuth app in {sourceName}'s developer console.
                          </p>
                        </div>

                        {/* Help section with hover info */}
                        <div className="flex items-start gap-2 group">
                          <div className="relative">
                            <HelpCircle className={cn(
                              "h-4 w-4 mt-0.5 flex-shrink-0 transition-all cursor-help",
                              isDark
                                ? "text-gray-500 group-hover:text-blue-400"
                                : "text-gray-400 group-hover:text-blue-600"
                            )} />

                            {/* Hover tooltip */}
                            <div className={cn(
                              "absolute left-0 top-6 z-50 w-80 p-4 rounded-lg shadow-xl",
                              "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
                              "transition-all duration-200 transform group-hover:translate-y-0 translate-y-1",
                              isDark
                                ? "bg-gray-800 border border-gray-700"
                                : "bg-white border border-gray-200"
                            )}>
                              <div className="space-y-3">
                                <p className={cn(
                                  "text-sm font-medium",
                                  isDark ? "text-white" : "text-gray-900"
                                )}>
                                  What are OAuth credentials?
                                </p>
                                <p className={cn(
                                  "text-xs leading-relaxed",
                                  isDark ? "text-gray-400" : "text-gray-600"
                                )}>
                                  OAuth credentials (Client ID and Client Secret) are like a special key that allows Airweave to securely access your {sourceName} data on your behalf. You create these in {sourceName}'s developer settings, and they ensure only authorized applications can connect to your account.
                                </p>
                                <div className={cn(
                                  "text-xs space-y-1 pt-2 border-t",
                                  isDark ? "border-gray-700" : "border-gray-200"
                                )}>
                                  <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                    <span className="font-medium">Client ID:</span> Public identifier for your app
                                  </p>
                                  <p className={cn(isDark ? "text-gray-500" : "text-gray-500")}>
                                    <span className="font-medium">Client Secret:</span> Private key (keep this secure!)
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="text-sm">
                            <span className={cn(
                              "font-medium",
                              isDark ? "text-gray-400" : "text-gray-600"
                            )}>
                              Need help setting up OAuth?
                            </span>
                            <a
                              href="https://docs.airweave.ai/integrations/oauth-setup"
                              target="_blank"
                              rel="noopener noreferrer"
                              className={cn(
                                "ml-2 inline-flex items-center gap-1 font-medium hover:underline",
                                isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                              )}
                            >
                              View documentation
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        </div>

                        <div className="space-y-3">
                          <input
                            type="text"
                            placeholder="Client ID"
                            value={clientId}
                            onChange={(e) => setClientId(e.target.value)}
                            className={cn(
                              "w-full px-4 py-2.5 rounded-lg text-sm",
                              "border bg-transparent",
                              "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
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
                              "w-full px-4 py-2.5 rounded-lg text-sm",
                              "border bg-transparent",
                              "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                              isDark
                                ? "border-gray-800 text-white placeholder:text-gray-600"
                                : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                            )}
                          />
                        </div>
                      </div>
                    ) : (
                      // For optional OAuth sources, show toggle
                      <>
                        <div className="space-y-3">
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

                          {/* Help text with hover for optional OAuth */}
                          <div className="flex items-start gap-2 group ml-13">
                            <div className="relative">
                              <HelpCircle className={cn(
                                "h-3.5 w-3.5 mt-0.5 flex-shrink-0 transition-all cursor-help",
                                isDark
                                  ? "text-gray-600 group-hover:text-blue-400"
                                  : "text-gray-400 group-hover:text-blue-600"
                              )} />

                              {/* Hover tooltip */}
                              <div className={cn(
                                "absolute left-0 top-5 z-50 w-72 p-3 rounded-lg shadow-xl",
                                "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
                                "transition-all duration-200 transform group-hover:translate-y-0 translate-y-1",
                                isDark
                                  ? "bg-gray-800 border border-gray-700"
                                  : "bg-white border border-gray-200"
                              )}>
                                <p className={cn(
                                  "text-xs leading-relaxed",
                                  isDark ? "text-gray-400" : "text-gray-600"
                                )}>
                                  By default, Airweave uses its own OAuth app to connect. Enable this if you want to use your own OAuth application to show your own name and logo.
                                </p>
                              </div>
                            </div>

                            <p className={cn(
                              "text-xs",
                              isDark ? "text-gray-500" : "text-gray-500"
                            )}>
                              Optional: Use your own OAuth app for enhanced control.{' '}
                              <a
                                href="https://docs.airweave.ai/integrations/custom-oauth"
                                target="_blank"
                                rel="noopener noreferrer"
                                className={cn(
                                  "inline-flex items-center gap-0.5 font-medium hover:underline",
                                  isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                                )}
                              >
                                Learn more
                                <ExternalLink className="h-2.5 w-2.5" />
                              </a>
                            </p>
                          </div>
                        </div>

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
                                "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
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
                                "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "border-gray-800 text-white placeholder:text-gray-600"
                                  : "border-gray-200 text-gray-900 placeholder:text-gray-400"
                              )}
                            />
                          </div>
                        )}
                      </>
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
            onClick={() => handleBackFromSourceConfig()}
            className={cn(
              "px-6 py-2 rounded-lg text-sm font-medium transition-colors",
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
                "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all",
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
