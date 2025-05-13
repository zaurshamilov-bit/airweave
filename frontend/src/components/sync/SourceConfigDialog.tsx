import { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, Check, ArrowLeft, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";

// Props passed from ConnectToSourceFlow
interface SourceConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete: (connectionId: string) => void;  // Called with source connection ID or "oauth2_prefix"
  shortName: string;  // Source short name
  name: string;  // Source display name
  sourceDetails?: SourceDetails;  // Source details including auth fields
  collectionId?: string;  // Collection to connect to
}

// Field definition from backend API
interface ConfigField {
  name: string;
  title: string;
  description: string;
  type: string;
}

// Source details from backend API
interface SourceDetails {
  name: string;
  description: string;
  short_name: string;
  auth_fields?: {
    fields: ConfigField[];
  };
  auth_type?: string;
}

export const SourceConfigDialog = ({
  open,
  onOpenChange,
  onComplete,
  shortName,
  name,
  sourceDetails: passedSourceDetails,
  collectionId
}: SourceConfigDialogProps) => {
  // =========================================
  // STATE MANAGEMENT
  // =========================================
  const [step, setStep] = useState(1);
  const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
  const [config, setConfig] = useState<{ name: string; auth_fields: Record<string, string> }>({
    name: "",
    auth_fields: {}
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sourceConnectionConfig, setSourceConnectionConfig] = useState<{
    name: string;
    short_name: string;
    sourceDetails?: any;
    collectionId?: string;
    onConfigComplete?: (connectionId: string) => void;
  } | null>(null);

  // =========================================
  // INITIALIZATION & CLEANUP
  // =========================================

  // Initialize from passed source details
  useEffect(() => {
    if (passedSourceDetails) {
      console.log("📋 [SourceConfigDialog] Using passed source details");
      setSourceDetails(passedSourceDetails);

      // Initialize config fields from source definition
      if (passedSourceDetails.auth_fields?.fields) {
        const initialConfig: Record<string, string> = {};
        passedSourceDetails.auth_fields.fields.forEach((field: ConfigField) => {
          initialConfig[field.name] = "";
        });
        setConfig({
          name: `My ${name} Connection`,
          auth_fields: initialConfig
        });
      }
    }
  }, [passedSourceDetails, name]);

  // Fetch source details if not passed
  useEffect(() => {
    if (open && !passedSourceDetails) {
      fetchSourceDetails();
    }
  }, [open, shortName, passedSourceDetails]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setStep(1);
      setIsSubmitting(false);
    }
  }, [open]);

  const fetchSourceDetails = async () => {
    try {
      setIsLoading(true);
      console.log("🔍 [SourceConfigDialog] Fetching source details for:", shortName);

      const response = await apiClient.get(`/sources/detail/${shortName}`);
      if (!response.ok) {
        throw new Error("Failed to fetch source details");
      }

      const data = await response.json();
      setSourceDetails(data);
      console.log("📥 [SourceConfigDialog] Received source details");

      // Initialize config
      if (data.auth_fields?.fields) {
        const initialConfig: Record<string, string> = {};
        data.auth_fields.fields.forEach((field: ConfigField) => {
          initialConfig[field.name] = "";
        });
        setConfig({
          name: `My ${name} Connection`,
          auth_fields: initialConfig
        });
      } else {
        // No config fields - dialog shouldn't be open
        console.log("⚠️ [SourceConfigDialog] Source has no config fields - closing dialog");
        onOpenChange(false);
      }
    } catch (error) {
      console.error("❌ [SourceConfigDialog] Error fetching source details:", error);
      toast.error("Failed to load source configuration");
    } finally {
      setIsLoading(false);
    }
  };

  // =========================================
  // SUBMIT HANDLER - KEY INTEGRATION POINT
  // =========================================
  const handleSubmit = async () => {
    if (!validateConfig()) return;

    try {
      setIsSubmitting(true);
      console.log("🚀 [SourceConfigDialog] Submitting config");

      // BRANCH 1: OAUTH2 SOURCES
      if (sourceDetails?.auth_type?.startsWith('oauth2')) {
        console.log("🔐 [SourceConfigDialog] OAuth2 source - storing config for later");

        // Store config fields in session storage for AuthCallback.tsx to use
        sessionStorage.setItem(`oauth2_config_${shortName}`, JSON.stringify({
          connection_name: config.name,
          auth_fields: config.auth_fields
        }));

        // Signal to ConnectToSourceFlow that OAuth flow should continue
        toast.success("Configuration saved, redirecting to authorization...");
        onComplete("oauth2_" + shortName);
        onOpenChange(false);
        return;
      }

      // BRANCH 2: CONFIG_CLASS / API_KEY SOURCES
      // Direct creation of source connection with auth fields
      console.log("🛠️ [SourceConfigDialog] Config class source - creating source connection directly");

      if (!collectionId) {
        throw new Error("Collection ID is required");
      }

      // Create source connection with config fields
      const sourceConnectionPayload = {
        name: config.name,
        short_name: shortName,
        collection: collectionId,
        auth_fields: config.auth_fields,
        sync_immediately: true
      };

      console.log("📤 [SourceConfigDialog] Creating source connection");
      const response = await apiClient.post(
        `/source-connections/`,
        sourceConnectionPayload
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to create source connection: ${errorText}`);
      }

      const data = await response.json();
      console.log("✅ [SourceConfigDialog] Source connection created with ID:", data.id);

      toast.success("Connection created successfully!");

      // Return the source connection ID to ConnectToSourceFlow
      onComplete(data.id);
      onOpenChange(false);
    } catch (error) {
      console.error("❌ [SourceConfigDialog] Error:", error);
      toast.error(error instanceof Error ? error.message : "Failed to create connection");
    } finally {
      setIsSubmitting(false);
    }
  };

  // =========================================
  // VALIDATION & NAVIGATION
  // =========================================
  const validateConfig = () => {
    console.log("🔍 [SourceConfigDialog] Validating config");

    if (!config.name.trim()) {
      toast.error("Please enter a name for your connection");
      return false;
    }

    // Validate all required fields
    const missingFields = sourceDetails?.auth_fields?.fields.filter(
      field => !config.auth_fields[field.name]?.trim()
    );

    if (missingFields && missingFields.length > 0) {
      toast.error(`Please fill in: ${missingFields.map(f => f.title).join(", ")}`);
      return false;
    }

    return true;
  };

  const handleBack = () => setStep(1);

  const handleNext = () => {
    if (validateConfig()) setStep(2);
  };

  // Helper to mask sensitive values in review screen
  const maskSensitiveValue = (value: string) => {
    if (!value) return '';
    return value.slice(0, 3) + '*'.repeat(Math.max(value.length - 3, 3));
  };

  // =========================================
  // RENDER UI
  // =========================================
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="relative">
            <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-primary/20">
              <div
                style={{ width: `${(step / 2) * 100}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-primary transition-all duration-500"
              />
            </div>
          </div>
        </div>

        {/* Configuration step */}
        {step === 1 && (
          <div className="space-y-6 animate-in slide-in-from-right">
            {isLoading ? (
              <div className="flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : sourceDetails ? (
              <>
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold">Configure {sourceDetails.name}</h2>
                  <p className="text-muted-foreground">
                    {sourceDetails.description?.split('\n')[0]}
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Connection Name</Label>
                    <Input
                      id="name"
                      value={config.name}
                      onChange={(e) => setConfig({ ...config, name: e.target.value })}
                      placeholder="Enter a name for this connection"
                    />
                  </div>

                  {sourceDetails.auth_fields?.fields.map((field) => (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={field.name}>
                        {field.title}
                        {field.description && (
                          <span className="text-xs text-muted-foreground ml-2">
                            ({field.description})
                          </span>
                        )}
                      </Label>
                      <Input
                        id={field.name}
                        type={field.type === "string" ? "text" : field.type}
                        value={config.auth_fields[field.name] || ""}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            auth_fields: {
                              ...config.auth_fields,
                              [field.name]: e.target.value
                            }
                          })
                        }
                        placeholder={`Enter ${field.title.toLowerCase()}`}
                      />
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center text-muted-foreground">
                Failed to load configuration. Please try again.
              </div>
            )}
          </div>
        )}

        {/* Review step */}
        {step === 2 && sourceDetails && (
          <div className="space-y-6 animate-in slide-in-from-right">
            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Review Configuration</h2>
              <p className="text-muted-foreground">
                Review your configuration and complete setup.
              </p>
            </div>
            <div className="space-y-4 rounded-lg border p-4">
              <div className="grid gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Connection Name</p>
                  <p className="font-medium">{config.name}</p>
                </div>
                {sourceDetails.auth_fields?.fields.map((field) => (
                  <div key={field.name}>
                    <p className="text-sm text-muted-foreground">{field.title}</p>
                    <p className="font-medium">
                      {field.type === "password" || field.name.toLowerCase().includes('key') || field.name.toLowerCase().includes('token')
                        ? maskSensitiveValue(config.auth_fields[field.name])
                        : config.auth_fields[field.name]}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        <div className="flex justify-between mt-8">
          {step > 1 && (
            <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
          )}

          {step === 1 ? (
            <Button
              className="ml-auto"
              onClick={handleNext}
              disabled={isLoading}
            >
              Next <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button
              className="ml-auto"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {sourceDetails?.auth_type?.startsWith('oauth2')
                    ? "Saving Configuration..."
                    : "Creating Connection..."}
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Complete Setup
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
