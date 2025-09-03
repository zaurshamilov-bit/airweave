import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Loader2, Key, Cloud, Link } from 'lucide-react';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

export const SourceConfigView: React.FC = () => {
  const {
    collectionId,
    collectionName,
    selectedSource,
    sourceName,
    authMode,
    setAuthMode,
    setAuthConfig,
    setConfigFields,
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

  const handleCreate = async () => {
    setIsCreating(true);

    try {
      // Build the request payload based on auth mode
      const payload: any = {
        name: `${sourceName} - ${collectionName}`,
        description: `${sourceName} connection for ${collectionName}`,
        short_name: selectedSource,
        collection: collectionId,
        auth_mode: authMode,
        sync_immediately: true,
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
      } else if (authMode === 'oauth2') {
        if (useOwnCredentials) {
          if (!clientId || !clientSecret) {
            toast.error('Please provide OAuth client credentials');
            setIsCreating(false);
            return;
          }
          payload.client_id = clientId;
          payload.client_secret = clientSecret;
        }
        // Set redirect URL for OAuth
        payload.redirect_url = `${window.location.origin}?oauth_return=true`;
      }

      // Create the source connection
      const response = await apiClient.post('/source-connections', payload);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create connection');
      }

      const result = await response.json();

      // Check if OAuth flow is needed
      if (result.authentication_url) {
        // Store OAuth state and authentication URL
        setOAuthData(
          result.id, // Using connection ID as state
          payload.redirect_url || `${window.location.origin}?oauth_return=true`,
          result.authentication_url
        );

        // Move to OAuth redirect view where user can copy URL or connect directly
        setStep('oauth-redirect');
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

  const renderAuthFields = () => {
    if (authMode === 'direct_auth') {
      // For now, show generic API key field
      // In production, this would be dynamic based on source requirements
      return (
        <div className="space-y-4">
          <div>
            <Label htmlFor="api-key">API Key / Access Token</Label>
            <Textarea
              id="api-key"
              placeholder="Enter your API key, access token, or credentials"
              value={authFields.api_key || authFields.access_token || authFields.personal_access_token || ''}
              onChange={(e) => {
                // Try to detect the type of credential
                const value = e.target.value;
                let fieldName = 'api_key';

                // Common patterns for different auth field names
                if (selectedSource === 'github') {
                  fieldName = 'personal_access_token';
                } else if (value.startsWith('Bearer ') || value.includes('ya29.')) {
                  fieldName = 'access_token';
                }

                setAuthFields({ [fieldName]: value });
              }}
              className="mt-1 font-mono text-sm"
              rows={3}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Paste your authentication credentials here
            </p>
          </div>
        </div>
      );
    }

    if (authMode === 'oauth2') {
      return (
        <div className="space-y-4">
          <div className="p-4 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <p className="text-sm">
              You'll be redirected to {sourceName} to authorize access.
            </p>
            <p className="text-xs mt-2 text-blue-700 dark:text-blue-300">
              After clicking Connect, you'll see the authentication URL that you can either:
              • Use yourself to connect directly
              • Copy and share with someone who needs to authorize
            </p>
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={useOwnCredentials}
                onChange={(e) => setUseOwnCredentials(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Use my own OAuth credentials</span>
            </label>

            {useOwnCredentials && (
              <div className="space-y-3 pl-6">
                <div>
                  <Label htmlFor="client-id">Client ID</Label>
                  <Input
                    id="client-id"
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    className="mt-1 font-mono text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="client-secret">Client Secret</Label>
                  <Input
                    id="client-secret"
                    type="password"
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    className="mt-1 font-mono text-sm"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="p-8">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setStep('source-select')}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-semibold">Connect {sourceName}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Configure authentication for your source
            </p>
          </div>
        </div>

        {/* Auth Mode Selection (if applicable) */}
        {!authMode && (
          <div className="space-y-3">
            <Label>Authentication Method</Label>
            <RadioGroup value={authMode} onValueChange={(v: any) => setAuthMode(v)}>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="oauth2" id="oauth2" />
                <Label htmlFor="oauth2" className="flex items-center gap-2 cursor-pointer">
                  <Link className="w-4 h-4" />
                  OAuth2 (Browser)
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="direct_auth" id="direct_auth" />
                <Label htmlFor="direct_auth" className="flex items-center gap-2 cursor-pointer">
                  <Key className="w-4 h-4" />
                  API Key / Credentials
                </Label>
              </div>
            </RadioGroup>
          </div>
        )}

        {/* Auth Configuration */}
        {authMode && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              {authMode === 'oauth2' ? (
                <>
                  <Link className="w-4 h-4" />
                  <span>OAuth2 Authentication</span>
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  <span>API Credentials</span>
                </>
              )}
            </div>

            {renderAuthFields()}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => setStep('source-select')}
            disabled={isCreating}
            className="flex-1"
          >
            Back
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!authMode || isCreating}
            className="flex-1"
          >
            {isCreating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              'Connect'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
