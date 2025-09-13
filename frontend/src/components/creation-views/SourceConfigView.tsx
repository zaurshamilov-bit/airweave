import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollectionCreationStore, AuthMode } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Copy, ExternalLink, Check, User, Users, Mail, Link2, ChevronRight, Send, Info, HelpCircle, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { SourceAuthenticationView } from '@/components/shared/SourceAuthenticationView';
import { AuthMethodSelector } from './AuthMethodSelector';
import { AuthProviderSelector } from './AuthProviderSelector';
import { useAuthProvidersStore } from '@/lib/stores/authProviders';
import { ValidatedInput } from '@/components/ui/validated-input';
import { sourceConnectionNameValidation, getAuthFieldValidation, clientIdValidation, clientSecretValidation } from '@/lib/validation/rules';

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
  const navigate = useNavigate();

  const {
    collectionId,
    collectionName,
    selectedSource,
    sourceName,
    sourceConnectionName,
    authMode,
    setAuthMode,
    selectedAuthProvider,
    setSelectedAuthProvider,
    authProviderConfig,
    setAuthProviderConfig,
    setOAuthData,
    setConnectionId,
    setStep,
    handleBackFromSourceConfig,
    setSourceConnectionName,
    existingCollectionId,
    closeModal,
    reset,
    isAddingToExistingCollection
  } = useCollectionCreationStore();

  const { authProviderConnections, fetchAuthProviderConnections } = useAuthProvidersStore();

  const [isCreating, setIsCreating] = useState(false);
  const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [configData, setConfigData] = useState<Record<string, string>>({});
  const [useOwnCredentials, setUseOwnCredentials] = useState(false);
  // Initialize connection name from store or with source default
  const [connectionName, setConnectionName] = useState(
    sourceConnectionName || (sourceName ? `${sourceName} Connection` : '')
  );
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  // Update store when connection name changes
  useEffect(() => {
    // Only update if the value actually changed
    if (connectionName !== sourceConnectionName) {
      setSourceConnectionName(connectionName);
    }
  }, [connectionName]); // Only depend on connectionName changes

  const [connectionUrl, setConnectionUrl] = useState('');

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

  // Determine available auth methods based on source
  const getAvailableAuthMethods = (): AuthMode[] => {
    if (!sourceDetails) return [];

    const methods: AuthMode[] = [];

    // Check for direct auth/config auth
    if (sourceDetails.auth_type === 'api_key' || sourceDetails.auth_type === 'basic' || isConfigAuth()) {
      methods.push('direct_auth');
    }

    // Check for OAuth
    if (sourceDetails.auth_type?.startsWith('oauth2') || sourceDetails.auth_config_class?.includes('OAuth')) {
      methods.push('oauth2');
    }

    // Add external provider if any are connected
    if (authProviderConnections.length > 0) {
      methods.push('external_provider');
    }

    return methods;
  };

  // Fetch auth provider connections on mount
  useEffect(() => {
    fetchAuthProviderConnections();
  }, [fetchAuthProviderConnections]);

  // Fetch source details to understand config requirements
  useEffect(() => {
    const fetchSourceDetails = async () => {
      if (!selectedSource) return;

      try {
        const response = await apiClient.get(`/sources/detail/${selectedSource}`);
        if (response.ok) {
          const source = await response.json();
          setSourceDetails(source);

          // Only set auth mode if it hasn't been set yet (preserve user selection)
          if (!authMode) {
            // Determine available methods inline to avoid dependency issues
            const methods: AuthMode[] = [];
            if (source.auth_type === 'api_key' || source.auth_type === 'basic' ||
                (source.auth_type === 'config_class' && !source.auth_config_class?.includes('OAuth'))) {
              methods.push('direct_auth');
            }
            if (source.auth_type?.startsWith('oauth2') || source.auth_config_class?.includes('OAuth')) {
              methods.push('oauth2');
            }
            if (authProviderConnections.length > 0) {
              methods.push('external_provider');
            }

            // Default to direct credentials or OAuth, not auth provider
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
                // Config-based auth (like GitHub) uses direct_auth mode
                setAuthMode('direct_auth');
              }
            } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
              setAuthMode('direct_auth');
            } else if (source.auth_type?.startsWith('oauth2')) {
              setAuthMode('oauth2');
            } else if (methods.includes('direct_auth')) {
              // Prefer direct auth if available
              setAuthMode('direct_auth');
            } else if (methods.includes('oauth2')) {
              // Then OAuth
              setAuthMode('oauth2');
            } else if (methods.includes('external_provider')) {
              // Auth provider as last resort
              setAuthMode('external_provider');
            } else if (methods.length > 0) {
              // Set first available method as default
              setAuthMode(methods[0]);
            }
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
  }, [selectedSource]); // Don't re-run when authProviderConnections changes to preserve user selection

  // Check if form is valid for submission
  const isFormValid = () => {
    // Must have a valid connection name (4-42 characters)
    const trimmedName = connectionName.trim();
    if (!trimmedName || trimmedName.length < 4 || trimmedName.length > 42) return false;

    // Check auth mode specific requirements
    if (authMode === 'external_provider') {
      return !!selectedAuthProvider;
    } else if (authMode === 'direct_auth') {
      // Need auth fields filled
      if (sourceDetails?.auth_fields?.fields) {
        const requiredFields = sourceDetails.auth_fields.fields.filter(f => f.required);
        return requiredFields.every(field => authFields[field.name]?.trim());
      }
    } else if (authMode === 'oauth2') {
      // Check if custom credentials are required
      if (requiresCustomOAuth() || useOwnCredentials) {
        return !!(clientId.trim() && clientSecret.trim());
      }
    }

    return true;
  };

  const handleCreate = async () => {
    setIsCreating(true);

    try {
      // Validate connection name
      if (!connectionName.trim()) {
        toast.error('Please enter a connection name');
        setIsCreating(false);
        return;
      }

      const payload: any = {
        name: connectionName.trim(),
        description: `${sourceName} connection for ${collectionName}`,
        short_name: selectedSource,
        collection: collectionId,
        auth_mode: authMode || 'oauth2',
        // For direct auth (API key, config), sync immediately since we have credentials
        // For OAuth, don't sync until after authorization is complete
        // For external provider, sync immediately since we're using existing auth
        sync_immediately: authMode === 'direct_auth' || authMode === 'external_provider',
      };

      // Add config fields if any
      if (Object.keys(configData).length > 0) {
        payload.config_fields = configData;
      }

      // Handle different auth modes
      if (authMode === 'external_provider') {
        // External provider auth
        if (!selectedAuthProvider) {
          toast.error('Please select an auth provider');
          setIsCreating(false);
          return;
        }
        payload.auth_provider = selectedAuthProvider;
        if (authProviderConfig && Object.keys(authProviderConfig).length > 0) {
          payload.auth_provider_config = authProviderConfig;
        }
      } else if (authMode === 'direct_auth' && isConfigAuth()) {
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
      } else {
        // Direct auth, config auth, or external provider successful
        setConnectionId(result.id);

        // For direct token sources, navigate directly to collection detail
        // instead of showing the success screen
        const targetCollectionId = isAddingToExisting ? existingCollectionId : collectionId;
        if (targetCollectionId) {
          // Close the modal
          closeModal();

          // Navigate to collection detail with success params
          navigate(`/collections/${targetCollectionId}?status=success&source_connection_id=${result.id}`);

          // Reset store state after navigation
          setTimeout(() => {
            reset();
          }, 100);
        } else {
          // Fallback to success view if no collection ID
          setStep('success');
        }
      }

    } catch (error) {
      console.error('Error creating source connection:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create connection');
    } finally {
      setIsCreating(false);
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
              Connect your {sourceName || 'data source'} to sync and search its content
            </p>
          </div>

          {/* Connection created state - Use shared component */}
          {connectionUrl ? (
            <SourceAuthenticationView
              sourceName={sourceName}
              authenticationUrl={connectionUrl}
              showBorder={false}
            />
          ) : (
            <>
              {/* Form fields - Clean minimal design */}
              <div className="space-y-6">
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                    Name
                  </label>
                  <ValidatedInput
                    type="text"
                    value={connectionName}
                    onChange={(value) => {
                      setConnectionName(value);
                      setSourceConnectionName(value);
                    }}
                    placeholder="Enter connection name"
                    validation={sourceConnectionNameValidation}
                    className={cn(
                      "focus:border-gray-400 dark:focus:border-gray-600",
                      isDark
                        ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                        : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                    )}
                  />
                </div>

                {/* Auth Method Selection */}
                {sourceDetails && (
                  <AuthMethodSelector
                    selectedMethod={authMode}
                    onMethodChange={setAuthMode}
                    availableAuthMethods={getAvailableAuthMethods()}
                    hasAuthProviders={authProviderConnections.length > 0}
                  />
                )}

                {/* Auth Provider Selection */}
                {authMode === 'external_provider' && (
                  <AuthProviderSelector
                    selectedProvider={selectedAuthProvider}
                    onProviderSelect={setSelectedAuthProvider}
                    onConfigChange={setAuthProviderConfig}
                  />
                )}

                {/* Config-based auth fields (like GitHub) */}
                {authMode === 'direct_auth' && isConfigAuth() && sourceDetails?.auth_fields?.fields && (
                  <div className="space-y-4">
                    <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
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
                        <ValidatedInput
                          type={field.name.includes('password') || field.name.includes('token') ? 'password' : 'text'}
                          placeholder=""
                          value={authFields[field.name] || ''}
                          onChange={(value) => setAuthFields({ ...authFields, [field.name]: value })}
                          validation={getAuthFieldValidation(field.name)}
                          className={cn(
                            "focus:border-gray-400 dark:focus:border-gray-600",
                            isDark
                              ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                              : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Direct auth fields (API key, basic auth) */}
                {authMode === 'direct_auth' && !isConfigAuth() && sourceDetails?.auth_fields?.fields && (
                  <div className="space-y-4">
                    <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Authentication
                    </label>
                    {sourceDetails.auth_fields.fields.map((field) => (
                      <div key={field.name}>
                        <label className="block text-sm font-medium mb-1.5">
                          {field.title || field.name}
                          {field.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        <ValidatedInput
                          type={field.name.includes('password') || field.name.includes('key') || field.name.includes('token') ? 'password' : 'text'}
                          placeholder=""
                          value={authFields[field.name] || ''}
                          onChange={(value) => setAuthFields({ ...authFields, [field.name]: value })}
                          validation={getAuthFieldValidation(field.name)}
                          className={cn(
                            "focus:border-gray-400 dark:focus:border-gray-600",
                            isDark
                              ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                              : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                          )}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Config fields (optional additional configuration) */}
                {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 && (
                  <div className="space-y-4">
                    <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
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
                          placeholder=""
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
                          <ValidatedInput
                            type="text"
                            placeholder="Client ID"
                            value={clientId}
                            onChange={setClientId}
                            validation={clientIdValidation}
                            className={cn(
                              "focus:border-gray-400 dark:focus:border-gray-600",
                              isDark
                                ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                            )}
                          />
                          <ValidatedInput
                            type="password"
                            placeholder="Client Secret"
                            value={clientSecret}
                            onChange={setClientSecret}
                            validation={clientSecretValidation}
                            className={cn(
                              "focus:border-gray-400 dark:focus:border-gray-600",
                              isDark
                                ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
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
                            <ValidatedInput
                              type="text"
                              placeholder="Client ID"
                              value={clientId}
                              onChange={setClientId}
                              validation={clientIdValidation}
                              className={cn(
                                "focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                  : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                              )}
                            />
                            <ValidatedInput
                              type="password"
                              placeholder="Client Secret"
                              value={clientSecret}
                              onChange={setClientSecret}
                              validation={clientSecretValidation}
                              className={cn(
                                "focus:border-gray-400 dark:focus:border-gray-600",
                                isDark
                                  ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                                  : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
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
              disabled={isCreating || !isFormValid()}
              className={cn(
                "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                isFormValid() && !isCreating
                  ? "bg-blue-600 hover:bg-blue-700 text-white"
                  : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
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
