/**
 * AuthCallback.tsx
 *
 * This component handles the OAuth callback process after a user authorizes
 * an external service. It's the final leg of the OAuth flow, where we:
 *
 * 1. Receive the authorization code from the OAuth provider
 * 2. Exchange the code for a connection via the backend
 * 3. Create the collection (using previously stored details)
 * 4. Create the source connection with the OAuth credentials
 * 5. Redirect the user to the appropriate page
 *
 * Flow context:
 * - This page is loaded when returning from an OAuth provider (like Google, GitHub, etc.)
 * - The user previously started in ConnectFlow, which stored collection details
 * - After processing, the user is redirected to the collection detail page
 */

import React, { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { OAUTH_KEYS } from "@/lib/ConnectToSourceFlow";
import { redirectWithError } from "@/lib/error-utils";

/**
 * AuthCallback Component
 *
 * This component handles the final leg of the OAuth2 flow:
 * 1) Receives code from OAuth provider in URL
 * 2) Exchanges code for connection via /connections/oauth2/source/code
 * 3) Creates source connection using our custom endpoint
 * 4) Redirects to collection page with success/error status
 */
export function AuthCallback() {
  /** Access URL parameters, including the OAuth code */
  const [searchParams] = useSearchParams();
  /** Get the source short_name from URL */
  const { short_name } = useParams();
  /** For navigation after processing */
  const navigate = useNavigate();
  /** Access authentication context */
  const auth = useAuth();

  /** Track completion to prevent double-processing */
  const exchangeAttempted = useRef(false);
  /** Cache promise and result to avoid duplicate API calls */
  const exchangePromise = useRef<any>(null);
  /** Flag to track if we already have a response in progress */
  const responseInProgress = useRef(false);
  /** Track navigation to prevent double redirects */
  const [hasStartedNavigation, setHasStartedNavigation] = useState(false);
  /** State for displaying errors in the UI */
  const [error, setError] = useState<{ message: string, details?: string } | null>(null);
  /** Track if we're loading data */
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Helper to safely navigate only once
   * Prevents duplicate navigation attempts which can cause errors
   *
   * @param url - Destination URL
   * @param options - Navigation options
   */
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
    }, 100);
  };

  /**
   * Enhanced error handler that captures detailed error information
   * and handles navigation to error page
   *
   * @param errorMessage - Primary error message
   * @param errorDetails - Technical details about the error
   * @param sourceName - Name of the source service if available
   */
  const handleError = (errorMessage: string, errorDetails?: string, sourceName?: string) => {
    console.error('❌ [AuthCallback] Error handling OAuth callback:', errorMessage, errorDetails);

    // Create error object
    const error = new Error(errorMessage);
    if (errorDetails) {
      Object.defineProperty(error, 'stack', {
        value: errorDetails
      });
    }

    // Get return URL or default to dashboard
    const returnUrl = localStorage.getItem(OAUTH_KEYS.RETURN_URL) || "/dashboard";

    // Use the common error utility for consistent error handling
    if (typeof window !== 'undefined') {
      // Use window.location directly to ensure full navigation/reload
      redirectWithError(window.location, error, sourceName);
    } else {
      // Fallback to direct URL construction
      safeNavigate(`/dashboard?connected=error`, { replace: true });
    }
  };

  /**
   * Main effect that processes the OAuth callback
   * This is the core of the component that orchestrates all steps
   */
  useEffect(() => {
    const processOAuthCallback = async () => {
      console.log(`🔄 [AuthCallback] Processing OAuth callback for ${short_name}`);

      // Prevent duplicate processing with strict protection
      if (exchangeAttempted.current) {
        console.log('⏭️ [AuthCallback] Exchange already attempted, skipping');
        return;
      }

      // Set flag immediately to prevent race conditions
      exchangeAttempted.current = true;

      // STEP 1: Extract code and validate parameters
      const code = searchParams.get("code");
      const error = searchParams.get("error");

      // Basic validation of source short name
      if (!short_name) {
        console.error('❌ [AuthCallback] Missing source name in URL');
        handleError(
          "Missing source information",
          "The source identifier is missing from the callback URL",
          "unknown service"
        );
        return;
      }

      // Check for OAuth provider errors first
      if (error) {
        const errorDescription = searchParams.get("error_description") || 'Authorization denied by provider';
        const errorState = searchParams.get("state") || '';

        // Different error handling based on error type
        if (error === 'access_denied') {
          handleError(
            "Permission denied",
            `You didn't grant permission to access your ${short_name} account. ${errorDescription}`,
            short_name
          );
        } else {
          handleError(
            `OAuth provider error: ${error}`,
            errorDescription,
            short_name
          );
        }
        return;
      }

      if (!code) {
        console.error('❌ [AuthCallback] Missing authorization code');
        handleError(
          "Missing authorization code",
          "The authorization code is missing from the callback URL. This might indicate that the authorization process was interrupted.",
          short_name
        );
        return;
      }

      try {
        // Wait for auth to be ready before proceeding
        if (auth.isLoading) {
          console.log('⏳ [AuthCallback] Auth still loading, delaying processing');
          setTimeout(processOAuthCallback, 500);
          exchangeAttempted.current = false; // Reset flag to allow retry
          return;
        }

        // Ensure we have a valid token
        console.log('🔑 [AuthCallback] Getting authentication token');
        await auth.getToken();

        // STEP 2: Retrieve stored data
        // Get return URL and collection details
        const returnUrl = localStorage.getItem(OAUTH_KEYS.RETURN_URL);
        const collectionDetailsJson = localStorage.getItem(OAUTH_KEYS.COLLECTION_DETAILS);
        console.log('🔍 [AuthCallback] Retrieved from localStorage:', {
          returnUrl,
          hasCollectionDetails: !!collectionDetailsJson
        });

        const targetUrl = returnUrl || "/dashboard";
        let collectionDetails;

        try {
          if (collectionDetailsJson) {
            collectionDetails = JSON.parse(collectionDetailsJson);
          } else {
            throw new Error("No collection details found in localStorage");
          }
        } catch (e) {
          console.error('❌ [AuthCallback] Failed to parse collection details:', e);
          handleError(
            "Failed to parse collection details",
            e instanceof Error ? e.message : String(e),
            short_name
          );
          return;
        }

        // Validate collection details
        if (!collectionDetails || !collectionDetails.name) {
          console.error('❌ [AuthCallback] Invalid collection details:', collectionDetails);
          handleError(
            "Invalid collection details",
            "The collection information is missing or incomplete",
            short_name
          );
          return;
        }

        // Get stored OAuth config (if any)
        const storedConfig = await retrieveStoredConfig(short_name);

        // STEP 3: Exchange code for connection
        let connectionData;
        try {
          connectionData = await exchangeCodeForConnection(code, short_name, storedConfig);
          if (!connectionData || !connectionData.id) {
            throw new Error("No valid connection data received from code exchange");
          }
        } catch (error) {
          // Special handling for the "body stream already read" error
          if (error instanceof Error && error.message.includes("body stream already read")) {
            console.warn("🔶 [AuthCallback] Ignoring body stream already read error - this is a duplicate call");

            // If we're in a race condition and the other execution already has data, try to use it
            if (exchangePromise.current && exchangePromise.current.data) {
              console.log("🔄 [AuthCallback] Using previously parsed connection data");
              connectionData = exchangePromise.current.data;
            } else {
              const message = "Failed to process OAuth response - duplicate request detected";
              handleError(message, "The response from the OAuth provider was already processed.", short_name);
              return;
            }
          } else {
            const message = error instanceof Error ? error.message : String(error);
            handleError(
              "Failed to exchange authorization code",
              message,
              short_name
            );
            return;
          }
        }

        // STEP 4: Create collection
        let collection;
        try {
          collection = await createCollection(collectionDetails);
          if (!collection || !collection.readable_id) {
            throw new Error("Failed to create collection - missing ID in response");
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          handleError(
            "Failed to create collection",
            message,
            short_name
          );
          return;
        }

        const collectionId = collection.readable_id;

        // STEP 5: Create source connection
        try {
          await createSourceConnection(connectionData, short_name, collectionId);
          // Success - navigate back to collection
          safeNavigate(`/collections/${collectionId}?connected=success`, { replace: true });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          handleError(
            "Failed to create source connection",
            message,
            short_name
          );
        }
      } catch (error) {
        console.error('❌ [AuthCallback] OAuth exchange error:', error);
        handleError(
          "OAuth exchange error",
          error instanceof Error ? error.message : String(error),
          short_name
        );
      } finally {
        setIsLoading(false);
      }
    };

    processOAuthCallback();

    // Cleanup on unmount - remove localStorage items after navigation started
    return () => {
      if (hasStartedNavigation) {
        console.log('🧹 [AuthCallback] Cleaning up localStorage items');
        localStorage.removeItem(OAUTH_KEYS.RETURN_URL);
        localStorage.removeItem(OAUTH_KEYS.COLLECTION_ID);
        localStorage.removeItem(OAUTH_KEYS.COLLECTION_DETAILS);

        // Also clean up any stored OAuth configs
        if (short_name) {
          const storageKey = `oauth2_config_${short_name}`;
          sessionStorage.removeItem(storageKey);
        }
      }
    };
  }, [searchParams, short_name, navigate, auth]);

  /**
   * Retrieves previously stored OAuth configuration
   * This is config that was collected in ConnectFlow and stored for this step
   *
   * @param shortName - Source short name
   * @returns Configuration object or null if not found
   */
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
      return config;
    } catch (err) {
      console.error('❌ [AuthCallback] Failed to parse stored OAuth2 config:', err);
      return null;
    }
  };

  /**
   * Exchanges the OAuth code for a connection
   * Sends the authorization code to our backend, which exchanges it with the provider
   *
   * @param code - OAuth authorization code from provider
   * @param shortName - Source short name
   * @param storedConfig - Previously stored configuration (if any)
   * @returns Connection data from the backend
   */
  const exchangeCodeForConnection = async (code: string, shortName: string, storedConfig: any) => {
    console.log('🔄 [AuthCallback] Exchanging OAuth code for connection');

    // Prevent duplicate API calls to avoid response stream errors
    if (responseInProgress.current) {
      console.log('⚠️ [AuthCallback] Response already in progress, waiting for completion');
      // Wait for up to 2 seconds for existing request to complete
      for (let i = 0; i < 20; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (exchangePromise.current && exchangePromise.current.data) {
          console.log('✅ [AuthCallback] Existing request completed, using its data');
          return exchangePromise.current.data;
        }
      }
      throw new Error("Timed out waiting for OAuth response");
    }

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
      console.log('🔄 [AuthCallback] Using cached connection data');
      return exchangePromise.current.data;
    }

    // Set flag to indicate response is in progress
    responseInProgress.current = true;

    try {
      // Store both promise and result
      if (!exchangePromise.current) {
        // =====================================================================
        // BACKEND CONNECTION CREATION - IMPORTANT DATABASE OPERATION
        // This is where a new CONNECTION is created in the database
        // POST /connections/oauth2/source/code endpoint exchanges the OAuth code
        // and creates a connection record in connections.py
        // =====================================================================
        exchangePromise.current = { promise: apiClient.post(`/connections/oauth2/source/code`, payload) };
      }

      const response = await exchangePromise.current.promise;
      if (!response.ok) {
        let errorText = await response.text();

        // Try to parse as JSON if possible
        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.detail) {
            errorText = errorJson.detail;
          }
        } catch (e) {
          // Not JSON, use as is
        }

        console.error('❌ [AuthCallback] OAuth code exchange failed:', errorText);
        throw new Error(`OAuth code exchange failed: ${errorText}`);
      }

      // Need to clone the response to safely parse it
      // This prevents "body stream already read" errors on concurrent calls
      const responseData = await response.clone().json();

      // Store the parsed data
      exchangePromise.current.data = responseData;

      console.log('✅ [AuthCallback] OAuth code exchange successful, created connection:', responseData);
      return responseData;
    } catch (error) {
      console.error('❌ [AuthCallback] Failed to exchange code:', error);

      // If we have a "body stream already read" error and already have data, use it
      if (error instanceof Error &&
        error.message.includes("body stream already read") &&
        exchangePromise.current &&
        exchangePromise.current.data) {
        return exchangePromise.current.data;
      }

      // Enhance error with user-friendly message
      const enhancedError = new Error(
        `Failed to connect to ${shortName}: ${error instanceof Error ? error.message : String(error)}`
      );
      throw enhancedError;
    } finally {
      // Clear the in-progress flag
      responseInProgress.current = false;
    }
  };

  /**
   * Creates a collection using the stored collection details
   *
   * @param collectionDetails - Collection details from localStorage
   * @returns Created collection data
   */
  const createCollection = async (collectionDetails: any) => {
    console.log('🔄 [AuthCallback] Creating collection with details:', collectionDetails);

    if (!collectionDetails || !collectionDetails.name) {
      console.error('❌ [AuthCallback] Missing collection details');
      throw new Error("Missing collection details");
    }

    try {
      // First check if the collection already exists (when adding to existing collection)
      if (collectionDetails.readable_id) {
        console.log('🔍 [AuthCallback] Checking if collection already exists:', collectionDetails.readable_id);
        const checkResponse = await apiClient.get(`/collections/${collectionDetails.readable_id}`);

        if (checkResponse.ok) {
          // Collection already exists, return it
          const existingCollection = await checkResponse.json();
          console.log('✅ [AuthCallback] Using existing collection:', existingCollection);
          return existingCollection;
        }
        // If not found (404), continue to create a new one
        console.log('🔄 [AuthCallback] Collection not found, creating new one');
      }

      // =====================================================================
      // BACKEND COLLECTION CREATION - IMPORTANT DATABASE OPERATION
      // This is where a new COLLECTION is created in the database
      // POST /collections/ endpoint creates a persistent collection record
      // in collections.py
      // =====================================================================
      const collectionResponse = await apiClient.post('/collections/', collectionDetails);

      if (!collectionResponse.ok) {
        const errorText = await collectionResponse.text();
        console.error('❌ [AuthCallback] Failed to create collection:', errorText);
        throw new Error(`Failed to create collection: ${errorText}`);
      }

      const collection = await collectionResponse.json();
      console.log('✅ [AuthCallback] Collection created successfully:', collection);
      return collection;
    } catch (error) {
      console.error('❌ [AuthCallback] Collection creation error:', error);
      throw new Error(`Collection creation failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  /**
   * Creates a source connection linked to the OAuth connection
   *
   * @param connectionData - OAuth connection data from backend
   * @param shortName - Source short name
   * @param collectionId - Collection ID to link with
   * @returns Source connection data
   */
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

    try {
      // =====================================================================
      // BACKEND SOURCE CONNECTION CREATION - IMPORTANT DATABASE OPERATION
      // This is where a new SOURCE CONNECTION is created in the database
      // POST /connections/create-source-connection-from-oauth creates a
      // persistent source connection record in source_connections.py
      // linking the OAuth connection with the collection
      // =====================================================================
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
    } catch (error) {
      console.error('❌ [AuthCallback] Source connection creation error:', error);
      throw new Error(`Source connection creation failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  /**
   * Polls for the source connection to be available
   * Ensures the connection is ready before redirecting the user
   *
   * @param collectionId - Collection ID
   * @param connectionId - Connection ID to verify
   */
  const verifySourceConnectionExists = async (collectionId: string, connectionId: string): Promise<void> => {
    console.log('🔍 [AuthCallback] Polling for source connection availability...');

    // Maximum number of retry attempts
    const maxRetries = 5;
    // Delay between retry attempts (milliseconds)
    const retryDelay = 1000;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // =====================================================================
        // BACKEND SOURCE CONNECTION VERIFICATION - DATABASE CHECK
        // This is checking that the SOURCE CONNECTION exists in the database
        // GET /source-connections/ endpoint in source_connections.py
        // verifies the connection was successfully created
        // =====================================================================
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

  // Render loading state during processing or error state if an error occurred
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-muted-foreground text-lg font-medium mb-2">Completing connection...</p>
        <p className="text-sm text-muted-foreground">
          Creating integration between your collection and {short_name || "the service"}...
        </p>
        {isLoading && (
          <div className="mt-4 text-xs text-gray-500">
            This may take a few moments
          </div>
        )}
      </div>
    </div>
  );
}
