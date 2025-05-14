/**
 * error-utils.ts
 *
 * Utility functions for handling connection errors consistently across the application.
 * Uses localStorage to store error details and URL parameter just for signaling.
 */

import { NavigateFunction } from "react-router-dom";

// Storage key for error data
export const CONNECTION_ERROR_STORAGE_KEY = "airweave_connection_error";

/**
 * ErrorDetails interface
 * Defines the structure of error information stored in localStorage
 */
export interface ErrorDetails {
    serviceName?: string;
    errorMessage: string;
    errorDetails?: string;
    timestamp: number;
}

/**
 * Stores error details in localStorage and redirects to dashboard
 *
 * @param navigate - React Router navigate function or window.location
 * @param error - Error object or message
 * @param serviceName - Name of the service that failed (optional)
 */
export const redirectWithError = (
    navigateOrLocation: NavigateFunction | typeof window.location | Location,
    error: Error | string,
    serviceName?: string
) => {
    // Extract error information
    const errorObj = typeof error === 'string' ? new Error(error) : error;
    const errorMessage = errorObj.message || "Connection failed";
    const errorDetails = errorObj.stack || errorObj.message;

    console.error(`❌ [ErrorUtils] Error:`, errorObj);
    console.log(`🔔 [ErrorUtils] Service name:`, serviceName);

    // Create error details object
    const errorData: ErrorDetails = {
        serviceName,
        errorMessage,
        errorDetails,
        timestamp: Date.now()
    };

    // Store in localStorage (no size limitation)
    localStorage.setItem(CONNECTION_ERROR_STORAGE_KEY, JSON.stringify(errorData));
    console.log(`🔔 [ErrorUtils] Stored error details in localStorage:`, errorData);

    // Create URL with just the error flag (no sensitive data)
    const targetUrl = `/dashboard?connected=error`;
    console.log(`🧭 [ErrorUtils] Redirecting to error page: ${targetUrl}`);

    // Use appropriate navigation method based on type
    if (typeof navigateOrLocation === 'function') {
        // React Router navigate function
        navigateOrLocation(targetUrl, { replace: true });
    } else {
        // Window.location or Location object
        try {
            // Check if it's window.location (has href property)
            if ('href' in navigateOrLocation) {
                navigateOrLocation.href = targetUrl;
            } else {
                console.error('[ErrorUtils] Invalid navigation object:', navigateOrLocation);
                // Fallback to window.location
                window.location.href = targetUrl;
            }
        } catch (e) {
            console.error('[ErrorUtils] Navigation error:', e);
            // Absolute fallback
            window.location.href = targetUrl;
        }
    }
};

/**
 * Retrieves error details from localStorage
 *
 * @returns Error details or null if none found
 */
export const getStoredErrorDetails = (): ErrorDetails | null => {
    const storedError = localStorage.getItem(CONNECTION_ERROR_STORAGE_KEY);
    if (!storedError) return null;

    try {
        const errorData = JSON.parse(storedError) as ErrorDetails;

        // Validate basic structure
        if (!errorData.errorMessage || !errorData.timestamp) {
            console.error('[ErrorUtils] Invalid error data structure in localStorage');
            return null;
        }

        // Check if error is recent (less than 5 minutes old)
        const isFresh = Date.now() - errorData.timestamp < 5 * 60 * 1000;
        if (!isFresh) {
            console.log('[ErrorUtils] Discarding stale error data');
            localStorage.removeItem(CONNECTION_ERROR_STORAGE_KEY);
            return null;
        }

        return errorData;
    } catch (e) {
        console.error('[ErrorUtils] Failed to parse error data from localStorage', e);
        localStorage.removeItem(CONNECTION_ERROR_STORAGE_KEY);
        return null;
    }
};

/**
 * Clears error details from localStorage
 */
export const clearStoredErrorDetails = () => {
    localStorage.removeItem(CONNECTION_ERROR_STORAGE_KEY);
};
