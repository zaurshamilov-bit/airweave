/**
 * ConnectToSourceFlow.tsx - Data and API interaction layer for connecting sources to collections.
 */

/**
 * CRITICAL: For OAuth sources with auth fields, check auth_type FIRST before deciding connection path.
 * Store auth_fields in sessionStorage before OAuth flow. AuthCallback.tsx retrieves these later.
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { redirectWithError } from "@/lib/error-utils";

/**
 * Interface for source details returned from the API
 */
interface SourceDetails {
    name: string;
    description?: string;
    short_name: string;
    auth_type?: string;
    auth_fields?: {
        fields: any[];
    };
}

/**
 * Interface for collection details
 */
interface CollectionDetails {
    name: string;
    readable_id?: string;
}

/**
 * Interface for source configuration data
 * Collected by ConnectFlow and passed to initiateConnection
 */
interface SourceConfig {
    name: string;
    auth_fields: Record<string, string>;
}

/**
 * Props for the ConnectToSourceFlow component
 */
interface ConnectToSourceFlowProps {
    /** Short name identifier for the source type (e.g., "notion", "github") */
    sourceShortName: string;
    /** Display name of the source */
    sourceName: string;
    /** Collection details where source will be connected */
    collectionDetails: CollectionDetails;
    /** Optional callback when connection completes successfully */
    onComplete?: () => void;
    /** Optional callback when connection fails */
    onError?: (error: Error) => void;
}

/**
 * Interface for OAuth redirect information
 */
interface OAuthRedirectInfo {
    oauthRedirect: boolean;
    authUrl: string;
    collectionDetails: CollectionDetails;
}

// LocalStorage keys for OAuth flow data persistence
const OAUTH_RETURN_URL_KEY = "oauth_return_url";
const OAUTH_COLLECTION_ID_KEY = "oauth_collection_id";
const OAUTH_COLLECTION_DETAILS_KEY = "oauth_collection_details";

/**
 * Hook that provides all source connection functionality
 *
 * This hook is the core of the connection process, providing methods
 * to initiate connections and handle different authentication types.
 */
export const useConnectToSourceFlow = () => {
    const navigate = useNavigate();

    /**
     * Redirects to dashboard with error information using the common error utility
     */
    const redirectToErrorPage = (error: Error, sourceName?: string) => {
        // Use the common utility
        redirectWithError(navigate, error, sourceName);
    };

    /**
     * Unified connection handler that manages all connection flows
     */
    const handleConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
        sourceDetails?: SourceDetails | null,
        config?: { name: string; auth_fields: Record<string, string> },
        isNewCollection?: boolean,
        onSuccess?: (result: any) => void,
        onRedirect?: (url: string, collectionDetails: CollectionDetails) => void,
        onError?: (error: Error, source: string) => void
    ): Promise<any> => {
        try {
            // Validate required parameters
            if (!sourceShortName) {
                const error = new Error("Missing source identifier (sourceShortName)");
                console.error("❌ [ConnectToSourceFlow] Missing sourceShortName in handleConnection");

                if (onError) {
                    onError(error, sourceName || "the service");
                } else {
                    redirectToErrorPage(error, sourceName);
                }
                return;
            }

            console.log(`🔄 [ConnectToSourceFlow] Starting connection for source: ${sourceShortName}`);
            console.log(`📝 [ConnectToSourceFlow] Collection context: ${isNewCollection ? "Creating new collection" : "Using existing collection if available"}`);

            // Get source details if not provided
            let details = sourceDetails;
            if (!details) {
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (!response.ok) {
                    throw new Error(`Failed to get source details: ${await response.text()}`);
                }
                details = await response.json();
                console.log(`✅ [ConnectToSourceFlow] Fetched source details for ${sourceShortName}`);
            }

            const authType = details.auth_type;
            console.log(`🔍 [ConnectToSourceFlow] Source auth type: ${authType}`);

            // DECISION POINT: OAuth vs Direct Connection
            // Check for OAuth first (our fix for auth_fields + OAuth sources)
            if (authType && authType.startsWith("oauth2")) {
                console.log(`🔑 [ConnectToSourceFlow] Detected OAuth flow for ${sourceShortName}`);

                // Check if this OAuth source has auth fields that have been provided
                const hasAuthFields = details?.auth_fields?.fields && details.auth_fields.fields.length > 0;
                const hasProvidedConfig = config && Object.keys(config.auth_fields || {}).length > 0;

                console.log(`🔍 [ConnectToSourceFlow] OAuth source details:`, {
                    hasAuthFields,
                    hasProvidedConfig,
                    authFieldsCount: details?.auth_fields?.fields?.length || 0
                });

                // If we have config with auth_fields, store them for use after OAuth
                if (config) {
                    const storageKey = `oauth2_config_${sourceShortName}`;
                    const oauthConfig = {
                        name: config.name,
                        connection_name: config.name,
                        auth_fields: config.auth_fields
                    };
                    sessionStorage.setItem(storageKey, JSON.stringify(oauthConfig));
                    console.log(`📝 [ConnectToSourceFlow] Stored OAuth config for ${sourceShortName}`);
                }

                // Store isNewCollection flag for OAuth callback
                sessionStorage.setItem("oauth2_is_new_collection", isNewCollection ? "true" : "false");

                // Get OAuth URL and prepare for redirect
                try {
                    const redirectInfo = await initiateOAuthFlow(
                        sourceShortName,
                        sourceName,
                        collectionDetails
                    );

                    // Let the UI layer handle the actual redirect
                    if (onRedirect && redirectInfo.authUrl) {
                        console.log(`🔀 [ConnectToSourceFlow] Redirecting to OAuth provider for ${sourceShortName}`);
                        onRedirect(redirectInfo.authUrl, collectionDetails);
                        return redirectInfo;
                    }

                    return redirectInfo;
                } catch (error) {
                    console.error(`❌ [ConnectToSourceFlow] OAuth initiation error for ${sourceShortName}:`, error);
                    if (onError) {
                        onError(
                            error instanceof Error ? error : new Error(String(error)),
                            sourceShortName
                        );
                    } else {
                        redirectToErrorPage(
                            error instanceof Error ? error : new Error(String(error)),
                            sourceShortName
                        );
                    }
                    throw error;
                }
            }

            // DIRECT CONNECTION PATH
            let result;
            console.log(`🔄 [ConnectToSourceFlow] Using direct connection path for ${sourceShortName}`);

            if (config) {
                // Non-OAuth source WITH config fields
                console.log(`📋 [ConnectToSourceFlow] Creating configured source connection for ${sourceShortName}`);
                result = await createConfiguredSourceConnection(
                    sourceShortName,
                    config.name,
                    collectionDetails,
                    config.auth_fields,
                    isNewCollection
                );
            } else {
                // Check if source needs config but none was provided
                if (details.auth_fields?.fields && details.auth_fields.fields.length > 0) {
                    const error = new Error(
                        `Source ${sourceName} requires configuration. Use the SourceConfigView first.`
                    );
                    console.error(`❌ [ConnectToSourceFlow] Source ${sourceShortName} requires config fields but none provided`);

                    if (onError) {
                        onError(error, sourceShortName);
                    } else {
                        redirectToErrorPage(error, sourceShortName);
                    }
                    throw error;
                }

                // Non-OAuth source WITHOUT config fields
                console.log(`📋 [ConnectToSourceFlow] Creating direct source connection for ${sourceShortName}`);
                const collectionId = await createDirectSourceConnection(
                    sourceShortName,
                    sourceName,
                    collectionDetails,
                    isNewCollection
                );
                result = { collectionId };
            }

            // Connection created successfully
            console.log(`✅ [ConnectToSourceFlow] Connection created successfully for ${sourceShortName}`);
            if (onSuccess) {
                onSuccess(result);
            }

            return result;
        } catch (error) {
            console.error(`❌ [ConnectToSourceFlow] Connection error for ${sourceShortName}:`, error);
            if (onError) {
                onError(
                    error instanceof Error ? error : new Error(String(error)),
                    sourceShortName
                );
            } else {
                redirectToErrorPage(
                    error instanceof Error ? error : new Error(String(error)),
                    sourceShortName
                );
            }

            throw error;
        }
    };

    /**
     * Legacy method - creates a connection for a source that needs configuration
     */
    const createConfiguredSourceConnection = async (
        sourceShortName: string,
        connectionName: string,
        collectionDetails: { name: string; readable_id?: string },
        authFields: Record<string, string>,
        isNewCollection: boolean
    ) => {
        let collectionId = collectionDetails.readable_id;

        try {
            // Create collection if it doesn't exist
            if (collectionId) {
                try {
                    const response = await apiClient.get(`/collections/${collectionId}`);
                    if (response.ok) {
                        // Collection exists
                        if (isNewCollection) {
                            // If trying to create a new collection, error out
                            throw new Error(`Collection with ID "${collectionId}" already exists`);
                        }
                        // Otherwise proceed with existing collection
                    } else if (response.status === 404) {
                        // Collection doesn't exist, create it with the same readable_id
                        const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                        if (!collectionResponse.ok) {
                            throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                        }
                        const collection = await collectionResponse.json();
                        collectionId = collection.readable_id;
                    } else {
                        throw new Error(`Failed to verify collection: ${await response.text()}`);
                    }
                } catch (error) {
                    if (error instanceof Error && error.message.includes("404")) {
                        // Collection doesn't exist, create it with the EXACT same readable_id
                        const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                        if (!collectionResponse.ok) {
                            throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                        }
                        const collection = await collectionResponse.json();
                        collectionId = collection.readable_id;
                    } else {
                        throw error;
                    }
                }
            } else {
                // Create new collection
                const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                if (!collectionResponse.ok) {
                    throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                }
                const collection = await collectionResponse.json();
                collectionId = collection.readable_id;
            }

            // Create the source connection
            const payload = {
                name: connectionName,
                short_name: sourceShortName,
                collection: collectionId,
                auth_fields: authFields,
                sync_immediately: true,
            };

            const response = await apiClient.post('/source-connections/', payload);
            if (!response.ok) {
                throw new Error(`Failed to create connection: ${await response.text()}`);
            }

            return await response.json();
        } catch (error) {
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceShortName
            );
            throw error;
        }
    };

    /**
     * Creates a source connection without configuration
     */
    const createDirectSourceConnection = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails,
        isNewCollection?: boolean
    ) => {
        try {
            // First check if collection already exists
            let collectionId;
            if (collectionDetails.readable_id) {
                try {
                    const response = await apiClient.get(`/collections/${collectionDetails.readable_id}`);
                    if (response.ok) {
                        // Collection exists
                        if (isNewCollection) {
                            // If trying to create a new collection, error out
                            throw new Error(`Collection with ID "${collectionDetails.readable_id}" already exists`);
                        }
                        collectionId = collectionDetails.readable_id;
                        console.log(`✅ [ConnectToSourceFlow] Using existing collection: ${collectionId}`);
                    } else if (response.status === 404) {
                        // Create new collection with the exact details provided
                        const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                        if (!collectionResponse.ok) {
                            throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                        }
                        const collection = await collectionResponse.json();
                        collectionId = collection.readable_id;
                        console.log(`✅ [ConnectToSourceFlow] Created new collection: ${collectionId}`);
                    } else {
                        throw new Error(`Failed to verify collection: ${await response.text()}`);
                    }
                } catch (error) {
                    // Only proceed with creating a collection if the error was a 404
                    // or if we're not checking for an existing collection
                    if (error instanceof Error && error.message.includes("404")) {
                        // Create new collection with the EXACT same readable_id
                        const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                        if (!collectionResponse.ok) {
                            throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                        }
                        const collection = await collectionResponse.json();
                        collectionId = collection.readable_id;
                        console.log(`✅ [ConnectToSourceFlow] Created new collection: ${collectionId}`);
                    } else {
                        throw error;
                    }
                }
            } else {
                // Create new collection
                const collectionResponse = await apiClient.post("/collections/", collectionDetails);
                if (!collectionResponse.ok) {
                    throw new Error(`Failed to create collection: ${await collectionResponse.text()}`);
                }
                const collection = await collectionResponse.json();
                collectionId = collection.readable_id;
                console.log(`✅ [ConnectToSourceFlow] Created new collection: ${collectionId}`);
            }

            // Create the source connection
            const payload = {
                name: `My ${sourceName}`,
                short_name: sourceShortName,
                collection: collectionId,
                sync_immediately: true
            };

            console.log(`📝 [ConnectToSourceFlow] Creating source connection for ${sourceShortName} in collection ${collectionId}`);
            const response = await apiClient.post("/source-connections/", payload);
            if (!response.ok) {
                throw new Error(`Failed to create source connection: ${await response.text()}`);
            }

            return collectionId;
        } catch (error) {
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceShortName
            );
            throw error;
        }
    };

    /**
     * Initiates OAuth flow for OAuth-based sources
     */
    const initiateOAuthFlow = async (
        sourceShortName: string,
        sourceName: string,
        collectionDetails: CollectionDetails
    ): Promise<OAuthRedirectInfo> => {
        try {
            // Store data for after OAuth redirect
            localStorage.setItem(OAUTH_RETURN_URL_KEY, `/dashboard`);
            localStorage.setItem(OAUTH_COLLECTION_DETAILS_KEY, JSON.stringify(collectionDetails));

            const storageKey = `oauth2_config_${sourceShortName}`;

            // Only create new config if none exists
            if (!sessionStorage.getItem(storageKey)) {
                const connectionConfig = {
                    name: `${sourceName} Connection`,
                    connection_name: `${sourceName} Connection`,
                    auth_fields: {} // Empty for sources without config fields
                };
                sessionStorage.setItem(storageKey, JSON.stringify(connectionConfig));
            }

            // Get stored config
            const storedConfig = sessionStorage.getItem(storageKey);
            let authFieldsParam = '';

            if (storedConfig) {
                try {
                    const configObj = JSON.parse(storedConfig);
                    console.log(`🔍 [OAuth] Retrieved stored config for ${sourceShortName}:`, configObj);

                    if (configObj.auth_fields) {
                        console.log(`🔍 [OAuth] Found auth_fields:`, configObj.auth_fields);
                        authFieldsParam = `&auth_fields=${encodeURIComponent(JSON.stringify(configObj.auth_fields))}`;
                        console.log(`🔍 [OAuth] Created authFieldsParam: ${authFieldsParam}`);
                    } else {
                        console.log(`⚠️ [OAuth] No auth_fields in stored config`);
                    }
                } catch (e) {
                    console.warn("Error parsing stored OAuth config", e);
                }
            }

            // Before the API request, log the complete URL
            const fullUrl = `/connections/oauth2/source/auth_url?short_name=${sourceShortName}${authFieldsParam}`;
            console.log(`🔄 [OAuth] Requesting auth URL with: ${fullUrl}`);

            // Get auth URL with auth_fields if available
            const resp = await apiClient.get(fullUrl);
            if (!resp.ok) {
                throw new Error(`Failed to retrieve auth URL: ${await resp.text()}`);
            }

            const authUrl = await resp.text();
            const cleanUrl = authUrl.replace(/^"|"$/g, ''); // Remove surrounding quotes

            return {
                oauthRedirect: true,
                authUrl: cleanUrl,
                collectionDetails
            };
        } catch (error) {
            redirectToErrorPage(
                error instanceof Error ? error : new Error(String(error)),
                sourceShortName
            );
            throw error;
        }
    };

    const performOAuthRedirect = (url: string) => {
        window.location.href = url;
    };

    /**
     * Helper function to create a collection
     *
     * @param collectionDetails Collection details including name and optional readable_id
     * @returns Created collection object with readable_id
     */
    const createCollection = async (collectionDetails: { name: string; readable_id?: string }) => {
        const response = await apiClient.post("/collections/", collectionDetails);
        if (!response.ok) {
            throw new Error(`Failed to create collection: ${await response.text()}`);
        }
        return await response.json();
    };

    return {
        handleConnection,
        performOAuthRedirect,
        redirectToErrorPage
    };
};

/**
 * ConnectToSourceFlow Component
 *
 * A component wrapper around the useConnectToSourceFlow hook.
 * Used to initiate a connection flow directly in component form.
 *
 * Note: This component starts the connection process immediately on mount
 * and is rarely used directly - typically the hook is preferred.
 */
export const ConnectToSourceFlow: React.FC<ConnectToSourceFlowProps> = ({
    sourceShortName,
    sourceName,
    collectionDetails,
    onComplete,
    onError
}) => {
    const { handleConnection } = useConnectToSourceFlow();

    // Start the connection process on mount
    useEffect(() => {
        handleConnection(
            sourceShortName,
            sourceName,
            collectionDetails,
            null,
            undefined,
            false, // Not a new collection by default
            (result) => {
                if (onComplete) onComplete();
            },
            (url, details) => {
                window.location.href = url;
            },
            (error, source) => {
                if (onError) onError(error);
            }
        );

        return () => { };
    }, [sourceShortName, sourceName, collectionDetails]);

    // No need to render anything - this is just a controller component
    return null;
};

/**
 * Export constants for use in other components like AuthCallback
 * These keys are used to store/retrieve data during the OAuth flow
 */
export const OAUTH_KEYS = {
    RETURN_URL: OAUTH_RETURN_URL_KEY,
    COLLECTION_ID: OAUTH_COLLECTION_ID_KEY,
    COLLECTION_DETAILS: OAUTH_COLLECTION_DETAILS_KEY
};

export default ConnectToSourceFlow;
