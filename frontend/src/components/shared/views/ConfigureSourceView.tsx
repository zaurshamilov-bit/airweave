import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";
import { apiClient } from "@/lib/api";
import { authenticateSource } from "@/lib/authenticate";

export interface ConfigureSourceViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: Record<string, any>;
    onError?: (error: Error | string, errorSource?: string) => void;
}

export const ConfigureSourceView: React.FC<ConfigureSourceViewProps> = ({
    onNext,
    onBack,
    onCancel,
    onComplete,
    viewData = {},
    onError,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);
    const [authValues, setAuthValues] = useState<Record<string, any>>({});
    const [configValues, setConfigValues] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [step, setStep] = useState<'auth' | 'config'>('auth');
    const [validationAttempted, setValidationAttempted] = useState(false);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [dialogState, setDialogState] = useState<any>(null);
    const [connectionName, setConnectionName] = useState<string>(
        viewData.connectionName || `${viewData.sourceName || ""} Connection`
    );

    // Extract data passed from previous views
    const {
        sourceName,
        sourceShortName,
        collectionId,
        collectionName,
        created_collection_id,
        created_collection_name
    } = viewData;

    // Helper function to check if a field is a token field that should be skipped
    const isTokenField = (fieldName: string): boolean => {
        const lowerName = fieldName.toLowerCase();
        return lowerName === 'refresh_token' || lowerName === 'access_token';
    };

    // Fetch source details including auth and config fields
    useEffect(() => {
        if (!sourceShortName) return;

        const fetchSourceDetails = async () => {
            setLoading(true);
            try {
                const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                if (response.ok) {
                    const data = await response.json();
                    setSourceDetails(data);
                    console.log("Source details loaded:", data);

                    // Initialize auth values with empty strings (skip token fields)
                    if (data.auth_fields && data.auth_fields.fields) {
                        const initialAuthValues: Record<string, any> = {};
                        // Handle auth_fields.fields as array of objects with name property
                        data.auth_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                // Auto-initialize token fields as null
                                initialAuthValues[field.name] = isTokenField(field.name) ? null : '';
                            }
                        });
                        setAuthValues(initialAuthValues);
                    }

                    // Initialize config values with empty strings
                    if (data.config_fields && data.config_fields.fields) {
                        const initialConfigValues: Record<string, any> = {};
                        data.config_fields.fields.forEach((field: any) => {
                            if (field.name) {
                                initialConfigValues[field.name] = '';
                            }
                        });
                        setConfigValues(initialConfigValues);
                    }
                } else {
                    const errorText = await response.text();
                    console.error(`Failed to load source details: ${errorText}`);
                    handleError(new Error(`Failed to load source details: ${errorText}`), "Source details fetch error");
                }
            } catch (error) {
                console.error("Error fetching source details:", error);
                handleError(error instanceof Error ? error : new Error(String(error)), "Source details fetch error");
            } finally {
                setLoading(false);
            }
        };

        fetchSourceDetails();
    }, [sourceShortName]);

    // Create a consistent error handler
    const handleError = (error: Error | string, errorSource?: string) => {
        console.error(`❌ [ConfigureSourceView] Error:`, error);

        // If onError is provided, use it first
        if (onError) {
            onError(error, errorSource || sourceName || sourceShortName);
        } else {
            // Otherwise redirect directly
            redirectWithError(navigate, error, errorSource || sourceName || sourceShortName);
        }
    };

    // Simplify validate auth fields - all fields are required
    const validateAuthFields = (): boolean => {
        const newErrors: Record<string, string> = {};
        let isValid = true;

        // All visualized fields are required
        if (sourceDetails?.auth_fields?.fields) {
            sourceDetails.auth_fields.fields
                .filter(field => field.name && !isTokenField(field.name))
                .forEach((field: any) => {
                    if (!authValues[field.name] || authValues[field.name].trim() === '') {
                        newErrors[field.name] = `${field.title || field.name} is required`;
                        isValid = false;
                    }
                });
        }

        setErrors(newErrors);
        logAuthFieldsStatus();
        return isValid;
    };

    // Simplify hasEmptyRequiredAuthFields - all fields are required
    const hasEmptyRequiredAuthFields = (): boolean => {
        if (!sourceDetails?.auth_fields?.fields) return false;

        return sourceDetails.auth_fields.fields
            .filter(field => field.name && !isTokenField(field.name))
            .some(field => !authValues[field.name] || authValues[field.name].trim() === '');
    };

    // Simplify the logging function - all fields are required
    const logAuthFieldsStatus = () => {
        if (!sourceDetails?.auth_fields?.fields) return;

        console.group('🔐 Auth Fields Status:');

        sourceDetails.auth_fields.fields
            .filter((field: any) => field.name && !isTokenField(field.name))
            .forEach((field: any) => {
                const value = authValues[field.name] || '';
                const isEmpty = !value || value.trim() === '';
                const status = isEmpty ? '❌ INVALID' : '✅ VALID';

                console.log(
                    `${field.title || field.name}: %c${status}%c | Required: %cYES%c | Value: %c${isEmpty ? '(empty)' : value}`,
                    status.includes('✅') ? 'color: green; font-weight: bold' : 'color: red; font-weight: bold',
                    'color: inherit',
                    'color: orange; font-weight: bold',
                    'color: inherit',
                    isEmpty ? 'color: gray; font-style: italic' : 'color: blue'
                );
            });

        console.log('Has empty fields:', hasEmptyRequiredAuthFields());
        console.groupEnd();
    };

    // Add to handleAuthFieldChange
    const handleAuthFieldChange = (key: string, value: string) => {
        setAuthValues(prev => {
            const newValues = {
                ...prev,
                [key]: value
            };

            // Log after value changes but before validation
            setTimeout(() => {
                console.log(`Field changed: ${key} => "${value}"`);
                logAuthFieldsStatus();
            }, 0);

            return newValues;
        });

        // If validation has been attempted, validate in real-time
        if (validationAttempted) {
            validateAuthFields();
        }

        // Clear error for this field if any
        if (errors[key]) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated[key];
                return updated;
            });
        }
    };

    const handleConfigFieldChange = (key: string, value: string) => {
        setConfigValues(prev => ({
            ...prev,
            [key]: value
        }));
        // Clear error for this field if any
        if (errors[key]) {
            setErrors(prev => {
                const updated = { ...prev };
                delete updated[key];
                return updated;
            });
        }
    };

    // Add this function to check if there are config fields
    const hasConfigFields = (): boolean => {
        return !!(sourceDetails?.config_fields?.fields &&
            sourceDetails.config_fields.fields.length > 0);
    };

    // Modify handleNextStep
    const handleNextStep = () => {
        console.log('🔄 Attempting to proceed to next step...');
        setValidationAttempted(true);
        const isValid = validateAuthFields();
        console.log(`Validation result: ${isValid ? '✅ VALID' : '❌ INVALID'}`);

        if (isValid) {
            if (hasConfigFields()) {
                console.log('✅ Proceeding to config step');
                setStep('config');
            } else {
                console.log('✅ No config fields, proceeding directly to connection');
                handleComplete();
            }
        } else {
            console.log('❌ Cannot proceed - validation failed');
        }
    };

    const handleComplete = async () => {
        if (!validateConfigFields()) {
            return;
        }

        setSubmitting(true);
        try {
            // Determine which collection we're using
            let collectionId = viewData.collectionId;

            // If we need to create a collection (it doesn't exist yet)
            if (viewData.created_collection_id && viewData.created_collection_name) {
                console.log(`🆕 Creating new collection: ${viewData.created_collection_name} (${viewData.created_collection_id})`);

                // Create collection via API
                const collectionResponse = await apiClient.post('/collections', {
                    name: viewData.created_collection_name,
                    readable_id: viewData.created_collection_id
                });

                if (!collectionResponse.ok) {
                    const errorText = await collectionResponse.text();
                    throw new Error(`Failed to create collection: ${errorText}`);
                }

                const collection = await collectionResponse.json();
                console.log(`✅ Collection created successfully: ${collection.readable_id}`);
                collectionId = collection.readable_id;
            }

            // Ensure we have a valid credential ID from the OAuth process
            if (!viewData.credentialId) {
                throw new Error("Missing credential ID. Authentication may not have completed properly.");
            }

            // Now create the source connection with the credential
            console.log(`🔌 Creating source connection in collection: ${collectionId}`);

            const sourceConnectionData = {
                name: viewData.connectionName || connectionName || `${sourceName} Connection`,
                short_name: sourceShortName,
                collection: collectionId,
                credential_id: viewData.credentialId,
                config_fields: configValues,
                sync_immediately: true
            };

            console.log(`📝 Source connection data:`, sourceConnectionData);

            const sourceConnectionResponse = await apiClient.post('/source-connections/', sourceConnectionData);

            if (!sourceConnectionResponse.ok) {
                const errorText = await sourceConnectionResponse.text();
                throw new Error(`Failed to create source connection: ${errorText}`);
            }

            const sourceConnection = await sourceConnectionResponse.json();
            console.log(`✅ Source connection created successfully: ${sourceConnection.id}`);

            // Clear credential from sessionStorage to prevent auto-reopening
            sessionStorage.removeItem('oauth_dialog_state');

            // Complete the process
            if (onComplete) {
                onComplete({
                    success: true,
                    message: "Source connected successfully",
                    source_short_name: sourceShortName,
                    collection_id: collectionId,
                    source_connection_id: sourceConnection.id,
                    isCompleted: true // Signal this is a final completion
                });
            }

            // Redirect to collection detail view
            navigate(`/collections/${collectionId}`);
        } catch (error) {
            handleError(error instanceof Error ? error : new Error(String(error)), "Source connection error");
        } finally {
            setSubmitting(false);
        }
    };

    // Add or update this function
    const validateConfigFields = (): boolean => {
        const newErrors: Record<string, string> = {};
        let isValid = true;

        // Check that we have either created_collection_id or collectionId
        if (!viewData.created_collection_id && !viewData.collectionId) {
            newErrors['collection'] = 'Missing collection information';
            isValid = false;
        }

        // Validate config fields if they're present
        if (sourceDetails?.config_fields?.fields) {
            sourceDetails.config_fields.fields
                .filter((field: any) => field.required)
                .forEach((field: any) => {
                    if (!configValues[field.name] || configValues[field.name].trim() === '') {
                        newErrors[field.name] = `${field.title || field.name} is required`;
                        isValid = false;
                    }
                });
        }

        setErrors(newErrors);
        return isValid;
    };

    // Log when the component loads auth fields
    useEffect(() => {
        if (sourceDetails?.auth_fields?.fields) {
            console.log('📋 Source auth fields loaded:');
            sourceDetails.auth_fields.fields.forEach((field: any) => {
                if (field.name && !isTokenField(field.name)) {
                    console.log(`- ${field.title || field.name} (required)`);
                }
            });

            logAuthFieldsStatus();
        }
    }, [sourceDetails]);

    // Create a new handler for the authenticate button
    const handleAuthenticate = async () => {
        if (hasEmptyRequiredAuthFields()) return;

        try {
            // Create a comprehensive dialog state object with all necessary data
            const dialogState = {
                // Source information
                sourceDetails,
                sourceShortName,

                // Collection information from viewData
                ...viewData,

                // Connection name
                connectionName,

                // Current auth values
                authValues,

                // UI state
                configureStep: step,
                dialogFlowStep: viewData.dialogFlowStep || 1,
                validationAttempted,

                // Location information
                originPath: window.location.pathname,

                // Additional context needed to restore dialog
                dialogMode: viewData.dialogMode || 'source-button',

                // Add timestamp for freshness checking
                timestamp: Date.now()
            };

            console.log("📊 FULL DIALOG STATE BEFORE OAUTH:", JSON.stringify(dialogState, null, 2));

            // Check if this is an OAuth flow
            const isOAuthFlow = sourceDetails.auth_type &&
                sourceDetails.auth_type.startsWith('oauth2');

            // Pass navigate to authenticateSource
            const result = await authenticateSource(dialogState, navigate);

            // Only set authenticated state for non-OAuth flows or if we got a credentialId
            if (result.success) {
                if (result.credentialId) {
                    // For non-OAuth flows, we update the auth state through onNext
                    onNext?.({
                        credentialId: result.credentialId,
                        isAuthenticated: true
                    });

                    // Only set authenticated for non-OAuth flows or when we have a credentialId
                    if (!isOAuthFlow || result.credentialId) {
                        setIsAuthenticated(true);
                        setValidationAttempted(true);
                        validateAuthFields();
                    }
                }
            }
        } catch (error) {
            console.error("Authentication error:", error);
            handleError(error instanceof Error ? error : new Error(String(error)), "Authentication error");
        }
    };

    // Reset authentication state when auth values change, but not for OAuth credentials
    useEffect(() => {
        // Only reset if we're not using an OAuth credential
        if (isAuthenticated && !viewData.credentialId) {
            setIsAuthenticated(false);
        }
    }, [authValues, viewData.credentialId]);

    // Replace the useEffect for handling credentials with this improved version
    useEffect(() => {
        // Check if we have credential information from restored dialog state
        if (viewData && viewData.credentialId) {
            console.log("🔍 FULL VIEW DATA IN CONFIGURE SOURCE:", JSON.stringify(viewData, null, 2));
            console.log("🔑 Setting authenticated state with credential:", viewData.credentialId);
            setIsAuthenticated(true);

            // Also add the credential_id to authValues if needed
            setAuthValues(prev => ({
                ...prev,
                credential_id: viewData.credentialId
            }));

            // Ensure validation is complete
            setValidationAttempted(true);
        }
    }, [viewData]);

    // Add to useEffect for initialization
    useEffect(() => {
        // Set the step based on viewData if available
        if (viewData && viewData.configureStep) {
            setStep(viewData.configureStep);
        }
    }, [viewData]);

    // Update when sourceName changes to set default - modify around line 330
    useEffect(() => {
        // Only update if viewData.connectionName changes
        if (viewData.connectionName) {
            console.log("📝 Restoring saved connection name:", viewData.connectionName);
            setConnectionName(viewData.connectionName);
        }
    }, [viewData.connectionName]);

    // Render the auth fields step
    const renderAuthStep = () => (
        <div className="space-y-6">
            {/* Add a flex container for the title and button */}
            <div className="flex justify-between items-center">
                <DialogTitle className="text-2xl font-semibold text-left">
                    Authenticate Source Connection
                </DialogTitle>

                <Button
                    onClick={handleAuthenticate}
                    disabled={loading || hasEmptyRequiredAuthFields() || isAuthenticated}
                    className={cn(
                        "px-4",
                        isAuthenticated
                            ? "bg-green-600 text-white opacity-100 pointer-events-none"
                            : "bg-blue-600 hover:bg-blue-700 text-white",
                        isAuthenticated ? "disabled:opacity-100 disabled:bg-green-600" : ""
                    )}
                >
                    {isAuthenticated ? "Authenticated" : "Authenticate"}
                </Button>
            </div>

            <DialogDescription className="text-muted-foreground mb-6">
                {sourceName ? `Set up authentication for ${sourceName}` : "Set up your source authentication"}
            </DialogDescription>

            {/* Add this right after the DialogDescription and before the auth fields section */}
            <div className="bg-muted p-6 rounded-lg mb-4">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-medium">Connection Name</h3>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium">Name</label>
                    <input
                        type="text"
                        className={cn(
                            "w-full p-2 rounded border",
                            isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300"
                        )}
                        placeholder="Enter a name for this connection"
                        value={connectionName}
                        onChange={(e) => setConnectionName(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                        A descriptive name for this connection. Defaults to "{sourceName} Connection".
                    </p>
                </div>
            </div>

            {/* Auth fields section */}
            <div className="bg-muted p-6 rounded-lg mb-4">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-medium">Authentication</h3>
                    {sourceDetails?.auth_config_class && (
                        <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                            {sourceDetails.auth_config_class}
                        </span>
                    )}
                </div>

                {/* Only show validation error message if validation has been attempted */}
                {validationAttempted && hasEmptyRequiredAuthFields() && (
                    <div className="mb-4 p-3 bg-red-500/10 rounded border border-red-500/20">
                        <p className="text-sm text-red-600">
                            <span className="font-medium">Error:</span> Please fill in all fields before proceeding.
                        </p>
                    </div>
                )}

                {/* Token notice if token fields are present */}
                {sourceDetails.auth_fields.fields.some((field: any) =>
                    field.name && isTokenField(field.name)
                ) && (
                        <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 mb-4">
                            <p className="text-sm">
                                <span className="font-medium">Note:</span> Access tokens and refresh tokens will be
                                automatically generated during OAuth authorization and don't need to be entered manually.
                            </p>
                        </div>
                    )}

                {/* Render auth fields (excluding token fields) - without asterisks */}
                {sourceDetails.auth_fields.fields
                    .filter((field: any) => field.name && !isTokenField(field.name))
                    .map((field: any) => (
                        <div key={field.name} className="space-y-2">
                            <label className="text-sm font-medium">
                                {field.title || field.name}
                            </label>
                            <input
                                type={field.type === 'password' ? 'password' : 'text'}
                                className={cn(
                                    "w-full p-2 rounded border",
                                    isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                    validationAttempted && errors[field.name] ? "border-red-500" : ""
                                )}
                                placeholder={field.description || ''}
                                value={authValues[field.name] || ''}
                                onChange={(e) => handleAuthFieldChange(field.name, e.target.value)}
                            />
                            {validationAttempted && errors[field.name] ? (
                                <p className="text-xs text-red-500">{errors[field.name]}</p>
                            ) : field.description ? (
                                <p className="text-xs text-muted-foreground">{field.description}</p>
                            ) : null}
                        </div>
                    ))}
            </div>

        </div>
    );

    // Render the config fields step
    const renderConfigStep = () => (
        <div className="space-y-6">
            <DialogTitle className="text-2xl font-semibold text-left mb-4">
                Configure Source Connection
            </DialogTitle>

            <DialogDescription className="text-muted-foreground mb-6">
                {sourceName ? `Configure ${sourceName} connection settings` : "Configure your source connection settings"}
            </DialogDescription>

            {/* Config fields section */}
            <div className="bg-muted p-6 rounded-lg mb-4">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-medium">Configuration</h3>
                    {sourceDetails?.config_class && (
                        <span className="text-xs text-muted-foreground bg-muted-foreground/20 px-2 py-1 rounded">
                            {sourceDetails.config_class}
                        </span>
                    )}
                </div>

                {sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 ? (
                    <div className="space-y-4">
                        {sourceDetails.config_fields.fields.map((field: any) => (
                            <div key={field.name} className="space-y-2">
                                <label className="text-sm font-medium">
                                    {field.title || field.name}
                                    {field.required && <span className="text-red-500 ml-1">*</span>}
                                </label>
                                <input
                                    type="text"
                                    className={cn(
                                        "w-full p-2 rounded border",
                                        isDark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-300",
                                        errors[field.name] ? "border-red-500" : ""
                                    )}
                                    placeholder={field.description || ''}
                                    value={configValues[field.name] || ''}
                                    onChange={(e) => handleConfigFieldChange(field.name, e.target.value)}
                                />
                                {errors[field.name] ? (
                                    <p className="text-xs text-red-500">{errors[field.name]}</p>
                                ) : field.description ? (
                                    <p className="text-xs text-muted-foreground">{field.description}</p>
                                ) : null}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="py-4 text-sm text-muted-foreground italic">
                        No configuration fields required for this source.
                    </div>
                )}
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 h-full flex flex-col">
                    {loading ? (
                        <div className="flex justify-center items-center py-8">
                            <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
                        </div>
                    ) : sourceDetails ? (
                        step === 'auth' ? renderAuthStep() : renderConfigStep()
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            No source configuration available
                        </div>
                    )}
                </div>
            </div>

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-between gap-3 p-6">
                    <div>
                        {step === 'auth' ? (
                            onBack && (
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={onBack}
                                    className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                                >
                                    Back
                                </Button>
                            )
                        ) : (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setStep('auth')}
                                className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                            >
                                Back
                            </Button>
                        )}
                    </div>
                    <div className="flex gap-3">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onCancel}
                            className={cn("px-6", isDark ? "border-gray-700" : "border-gray-300")}
                        >
                            Cancel
                        </Button>

                        {step === 'auth' ? (
                            <Button
                                type="button"
                                onClick={handleNextStep}
                                className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                                disabled={loading || !isAuthenticated}
                            >
                                {hasConfigFields() ? 'Next' : 'Connect'}
                            </Button>
                        ) : (
                            <Button
                                type="button"
                                onClick={handleComplete}
                                className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                                disabled={loading || submitting}
                            >
                                {submitting ? 'Connecting...' : 'Connect'}
                            </Button>
                        )}
                    </div>
                </DialogFooter>
            </div>
        </div>
    );
};

export default ConfigureSourceView;
