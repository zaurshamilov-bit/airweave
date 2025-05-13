import React, { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { OAUTH_KEYS } from "@/lib/ConnectToSourceFlow";

/**
 * This component handles the final leg of the OAuth2 flow:
 * 1) Receives code from OAuth provider in URL
 * 2) Exchanges code for connection via /connections/oauth2/source/code
 * 3) Creates source connection using our custom endpoint
 * 4) Redirects to collection page with success/error status
 */
export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const { short_name } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();

  // Track completion to prevent double-processing
  const exchangeAttempted = useRef(false);
  const exchangePromise = useRef(null);
  // Track navigation to prevent double redirects
  const [hasStartedNavigation, setHasStartedNavigation] = useState(false);

  // =========================================
  // NAVIGATION HELPER
  // =========================================
  const safeNavigate = (url: string, options = {}) => {
    if (hasStartedNavigation) {
      console.log('⏭️ [AuthCallback] Navigation already started, ignoring duplicate');
      return;
    }

    console.log('🧭 [AuthCallback] Starting navigation to:', url);
    setHasStartedNavigation(true);

    // Small timeout to ensure state update before navigation
    setTimeout(() => {
      navigate(url, options);
    }, 10);
  };

  // =========================================
  // MAIN OAUTH EXCHANGE FLOW
  // =========================================
  useEffect(() => {
    const processOAuthCallback = async () => {
      console.log(`🔄 [AuthCallback] Processing OAuth callback for ${short_name}`);

      // Prevent duplicate processing
      if (exchangeAttempted.current) {
        console.log('⏭️ [AuthCallback] Exchange already attempted, skipping');
        return;
      }

      // STEP 1: Extract code and validate parameters
      const code = searchParams.get("code");
      if (!code || !short_name) {
        console.error('❌ [AuthCallback] Missing code or source name');
        handleError("Missing required OAuth parameters");
        return;
      }

      try {
        // Wait for auth to be ready before proceeding
        if (auth.isLoading) {
          console.log('⏳ [AuthCallback] Auth still loading, delaying processing');
          setTimeout(processOAuthCallback, 500);
          return;
        }

        // Ensure we have a valid token
        console.log('🔑 [AuthCallback] Getting authentication token');
        await auth.getToken();

        // Mark exchange as attempted to prevent duplicates
        exchangeAttempted.current = true;

        // STEP 2: Retrieve stored data
        // Get return URL and collection ID
        const returnUrl = localStorage.getItem(OAUTH_KEYS.RETURN_URL);
        const collectionId = localStorage.getItem(OAUTH_KEYS.COLLECTION_ID);
        console.log('🔍 [AuthCallback] Retrieved from localStorage:', {
          returnUrl,
          collectionId
        });

        const targetUrl = returnUrl || "/dashboard";

        // Get stored OAuth config (if any)
        const storedConfig = await retrieveStoredConfig(short_name);

        // STEP 3: Exchange code for connection
        const connectionData = await exchangeCodeForConnection(code, short_name, storedConfig);

        // STEP 4: Create source connection
        if (collectionId) {
          await createSourceConnection(connectionData, short_name, collectionId);
          // Success - navigate back to collection
          safeNavigate(`${targetUrl}?connected=success`, { replace: true });
        } else {
          console.error('❌ [AuthCallback] No collection ID found in localStorage');
          handleError("Missing collection ID");
        }
      } catch (error) {
        console.error('❌ [AuthCallback] OAuth exchange error:', error);
        handleError(error instanceof Error ? error.message : String(error));
      }
    };

    processOAuthCallback();

    // Cleanup on unmount - remove localStorage items after navigation started
    return () => {
      if (hasStartedNavigation) {
        console.log('🧹 [AuthCallback] Cleaning up localStorage items');
        localStorage.removeItem(OAUTH_KEYS.RETURN_URL);
        localStorage.removeItem(OAUTH_KEYS.COLLECTION_ID);
      }
    };
  }, [searchParams, short_name, navigate, auth]);

  // =========================================
  // STEP FUNCTIONS
  // =========================================

  // Step 2: Get stored config from session storage
  const retrieveStoredConfig = async (shortName: string) => {
    const storageKey = `oauth2_config_${shortName}`;
    const storedConfigJson = sessionStorage.getItem(storageKey);

    if (!storedConfigJson) {
      console.log('⚠️ [AuthCallback] No stored config found in sessionStorage');
      return null;
    }

    try {
      const config = JSON.parse(storedConfigJson);
      console.log('📥 [AuthCallback] Found and parsed stored config');
      // Clean up after retrieving
      sessionStorage.removeItem(storageKey);
      return config;
    } catch (err) {
      console.error('❌ [AuthCallback] Failed to parse stored OAuth2 config:', err);
      return null;
    }
  };

  // Step 3: Exchange code for connection
  const exchangeCodeForConnection = async (code: string, shortName: string, storedConfig: any) => {
    console.log('🔄 [AuthCallback] Exchanging OAuth code for connection');

    // Prepare request payload with config fields if available
    const payload = {
      short_name: shortName,
      code,
      ...(storedConfig ? {
        auth_fields: storedConfig.auth_fields,
        connection_name: storedConfig.connection_name
      } : {})
    };

    console.log('📤 [AuthCallback] Sending code exchange payload:',
      { ...payload, code: '[REDACTED]' });

    // Check if we already have parsed data
    if (exchangePromise.current && exchangePromise.current.data) {
      return exchangePromise.current.data;
    }

    // Store both promise and result
    if (!exchangePromise.current) {
      exchangePromise.current = { promise: apiClient.post(`/connections/oauth2/source/code`, payload) };
    }

    const response = await exchangePromise.current.promise;
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ [AuthCallback] OAuth code exchange failed:', errorText);
      throw new Error(`OAuth code exchange failed: ${errorText}`);
    }

    const connectionData = await response.json();
    // Store the parsed data
    exchangePromise.current.data = connectionData;

    console.log('✅ [AuthCallback] OAuth code exchange successful, created connection:', connectionData);
    return connectionData;
  };

  // Step 4: Create source connection with connection
  const createSourceConnection = async (connectionData: any, shortName: string, collectionId: string) => {
    console.log('🔄 [AuthCallback] Creating source connection with connection ID:', connectionData.id);

    // Use connection name or fall back to source name
    const connectionName = connectionData.name || `${shortName} Connection`;

    // Prepare source connection payload
    const sourceConnectionPayload = {
      connection_id: connectionData.id,
      source_connection_in: {
        name: connectionName,
        short_name: shortName,
        collection: collectionId,
        sync_immediately: true
      }
    };

    // Use our new custom endpoint with connection_id
    const sourceConnectionResponse = await apiClient.post(
      `/connections/create-source-connection-from-oauth`,
      sourceConnectionPayload
    );

    if (!sourceConnectionResponse.ok) {
      const errorText = await sourceConnectionResponse.text();
      console.error('❌ [AuthCallback] Failed to create source connection:', errorText);
      throw new Error(`Failed to create source connection: ${errorText}`);
    }

    const sourceConnectionData = await sourceConnectionResponse.json();
    console.log('✅ [AuthCallback] Source connection created successfully:', sourceConnectionData);

    // Add polling to verify the connection is available before redirecting
    console.log('🔄 [AuthCallback] Verifying source connection availability...');
    await verifySourceConnectionExists(collectionId, sourceConnectionData.id);

    return sourceConnectionData;
  };

  // Add a new helper function to poll for the source connection
  const verifySourceConnectionExists = async (collectionId: string, connectionId: string): Promise<void> => {
    console.log('🔍 [AuthCallback] Polling for source connection availability...');

    // Maximum number of retry attempts
    const maxRetries = 5;
    // Delay between retry attempts (milliseconds)
    const retryDelay = 1000;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // Check if connections for this collection exist
        const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

        if (response.ok) {
          const connections = await response.json();

          // Check if our specific connection exists
          const connectionExists = connections.some((conn: any) => conn.id === connectionId);

          if (connectionExists) {
            console.log('✅ [AuthCallback] Source connection verified in collection!');
            return; // Connection exists, we can proceed
          }
        }

        console.log(`⏳ [AuthCallback] Connection not found yet, attempt ${attempt + 1}/${maxRetries}...`);

        // Wait before next attempt
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      } catch (error) {
        console.error('❌ [AuthCallback] Error checking for connection:', error);
        // Continue to next attempt despite error
      }
    }

    console.log('⚠️ [AuthCallback] Maximum polling attempts reached, proceeding anyway');
    // We'll proceed with navigation even if verification fails after max attempts
    // to avoid getting stuck in the callback page
  };

  // Error handler for all failure cases
  const handleError = (errorMessage: string) => {
    console.error('❌ [AuthCallback] Error handling OAuth callback:', errorMessage);

    // Get return URL or default to dashboard
    const returnUrl = localStorage.getItem(OAUTH_KEYS.RETURN_URL);
    const targetUrl = returnUrl || "/dashboard";
    console.log('🧭 [AuthCallback] Redirecting to error page:', targetUrl);

    // Navigate with error parameter
    safeNavigate(`${targetUrl}?connected=error`, { replace: true });
  };

  // =========================================
  // RENDER LOADING STATE
  // =========================================
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <p className="text-muted-foreground">Completing connection...</p>
        <p className="text-sm text-muted-foreground mt-2">
          Creating integration between your collection and {short_name}...
        </p>
      </div>
    </div>
  );
}
