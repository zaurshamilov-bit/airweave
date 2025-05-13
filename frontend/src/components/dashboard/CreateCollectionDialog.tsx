import React, { useState, useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod"; // Zod is a TypeScript-first schema validation library for form validation
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { Pencil, Info, Loader2 } from "lucide-react";
import { useConnectToSourceFlow } from "@/lib/ConnectToSourceFlow";

// Import the base components
import {
    Dialog,
    DialogContent,
    DialogPortal,
    DialogOverlay,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// Form schema validation with Zod
// Zod provides type-safe schema validation with TypeScript integration
const formSchema = z.object({
    name: z.string().min(4, "Name must be at least 4 characters").max(64, "Name must be less than 64 characters"),
    readable_id: z.string().optional().refine(
        (val) => !val || /^[a-z0-9-]+$/.test(val),
        { message: "Readable ID must contain only lowercase letters, numbers, and hyphens" }
    ),
});

// Generate a random suffix for the readable ID
const generateRandomSuffix = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < 6; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
};

// Helper to generate readable ID base from name (without suffix)
const generateReadableIdBase = (name: string): string => {
    if (!name || name.trim() === "") return "";

    // Convert to lowercase and replace spaces with hyphens
    let readable_id = name.toLowerCase().trim();

    // Replace any character that's not a letter, number, or space with nothing
    readable_id = readable_id.replace(/[^a-z0-9\s]/g, "");

    // Replace spaces with hyphens
    readable_id = readable_id.replace(/\s+/g, "-");

    // Ensure no consecutive hyphens
    readable_id = readable_id.replace(/-+/g, "-");

    // Trim hyphens from start and end
    readable_id = readable_id.replace(/^-|-$/g, "");

    return readable_id;
};

interface CreateCollectionDialogProps {
    isOpen: boolean;
    onClose: () => void;
    sourceId: string;
    sourceName: string;
    sourceShortName: string;
}

export const CreateCollectionDialog: React.FC<CreateCollectionDialogProps> = ({
    isOpen,
    onClose,
    sourceId,
    sourceName,
    sourceShortName,
}) => {
    console.log("🔄 [CreateCollectionDialog] Rendering with props:", {
        isOpen,
        sourceId,
        sourceName,
        sourceShortName
    });

    const navigate = useNavigate();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isCheckingSource, setIsCheckingSource] = useState(false);
    const [sourceDetails, setSourceDetails] = useState<any>(null);
    const defaultCollectionName = `My ${sourceName} Collection`;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Setup connection flow
    console.log("⚙️ [CreateCollectionDialog] Initializing connection flow hook");
    const { initiateConnection, renderConfigDialog } = useConnectToSourceFlow();
    const [createdCollectionId, setCreatedCollectionId] = useState<string | null>(null);

    // Use a ref to store the random suffix, so it persists across renders
    // but doesn't cause re-renders when accessed
    const randomSuffixRef = useRef(generateRandomSuffix());
    const previousNameRef = useRef(defaultCollectionName);
    const [userEditedId, setUserEditedId] = useState(false);

    // Directly manage input values to avoid the one-keypress delay
    const [nameValue, setNameValue] = useState(defaultCollectionName);
    const [readableIdValue, setReadableIdValue] = useState("");

    // Log state changes
    useEffect(() => {
        console.log("⚙️ [CreateCollectionDialog] Source details updated:", sourceDetails);
    }, [sourceDetails]);

    useEffect(() => {
        console.log("⚙️ [CreateCollectionDialog] Created collection ID updated:", createdCollectionId);
    }, [createdCollectionId]);

    // Get the source details when the dialog opens
    useEffect(() => {
        if (isOpen) {
            console.log("🔍 [CreateCollectionDialog] Dialog opened, fetching source details");

            const fetchSourceDetails = async () => {
                try {
                    setIsCheckingSource(true);
                    console.log("🔍 [CreateCollectionDialog] Fetching source details for:", sourceShortName);

                    const response = await apiClient.get(`/sources/detail/${sourceShortName}`);
                    if (response.ok) {
                        const data = await response.json();
                        console.log("📥 [CreateCollectionDialog] Received source details:", data);
                        setSourceDetails(data);
                    } else {
                        console.error("❌ [CreateCollectionDialog] Failed to fetch source details:",
                            await response.text());
                    }
                } catch (error) {
                    console.error("❌ [CreateCollectionDialog] Error fetching source details:", error);
                } finally {
                    setIsCheckingSource(false);
                }
            };

            fetchSourceDetails();
        } else {
            console.log("🪟 [CreateCollectionDialog] Dialog closed");
        }
    }, [isOpen, sourceShortName]);

    // Get the base readable ID from the name
    const getReadableId = (name: string) => {
        // If name is empty or just whitespace, return empty string
        if (!name || name.trim() === "") {
            return "";
        }

        const base = generateReadableIdBase(name);
        const result = base ? `${base}-${randomSuffixRef.current}` : "";
        console.log("🔄 [CreateCollectionDialog] Generated readable ID:", result, "from name:", name);
        return result;
    };

    // Initialize form with react-hook-form
    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            name: defaultCollectionName,
            readable_id: getReadableId(defaultCollectionName),
        },
    });

    // Reset form with default values when the dialog opens
    useEffect(() => {
        if (isOpen) {
            console.log("🔄 [CreateCollectionDialog] Resetting form with defaults");
            // Generate a new random suffix when dialog opens
            randomSuffixRef.current = generateRandomSuffix();
            console.log("🎲 [CreateCollectionDialog] Generated new random suffix:", randomSuffixRef.current);

            const defaultName = `My ${sourceName} Collection`;
            previousNameRef.current = defaultName;

            setNameValue(defaultName);
            const generatedId = getReadableId(defaultName);
            setReadableIdValue(generatedId);

            form.reset({
                name: defaultName,
                readable_id: generatedId,
            });
            console.log("🔄 [CreateCollectionDialog] Form reset with values:", {
                name: defaultName,
                readable_id: generatedId
            });

            // Reset user edit tracking
            setUserEditedId(false);
            setCreatedCollectionId(null);
        }
    }, [isOpen, sourceName, form]);

    // Handle name change - immediate update for both name and readable_id
    const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newName = e.target.value;
        console.log("✏️ [CreateCollectionDialog] Name changed to:", newName);

        setNameValue(newName);
        form.setValue("name", newName);

        // If the field was cleared, generate a new suffix for a fresh start
        if (previousNameRef.current && newName === "" && !userEditedId) {
            randomSuffixRef.current = generateRandomSuffix();
            console.log("🎲 [CreateCollectionDialog] Generated new random suffix:", randomSuffixRef.current);
        }

        // Only auto-generate if user hasn't manually edited it
        if (!userEditedId) {
            // If name is empty, set readable_id to empty as well
            if (!newName || newName.trim() === "") {
                const emptyId = "";
                console.log("✏️ [CreateCollectionDialog] Setting empty readable ID");
                setReadableIdValue(emptyId);
                form.setValue("readable_id", emptyId);
            } else {
                const newId = getReadableId(newName);
                console.log("✏️ [CreateCollectionDialog] Auto-updating readable ID to:", newId);
                setReadableIdValue(newId);
                form.setValue("readable_id", newId);
            }
        } else {
            console.log("✏️ [CreateCollectionDialog] Not auto-updating readable ID (user edited)");
        }

        // Update previous name reference
        previousNameRef.current = newName;
    };

    // Handle readable ID change
    const handleReadableIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newId = e.target.value;
        console.log("✏️ [CreateCollectionDialog] Readable ID changed to:", newId);

        setReadableIdValue(newId);
        form.setValue("readable_id", newId);

        // If name is empty, always allow editing the ID
        if (!nameValue || nameValue.trim() === "") {
            console.log("✏️ [CreateCollectionDialog] Setting user edited flag (name empty)");
            setUserEditedId(true);
            return;
        }

        const currentNameBase = generateReadableIdBase(nameValue);
        const currentFullId = `${currentNameBase}-${randomSuffixRef.current}`;

        // If value is different from auto-generated, user has edited it
        if (newId !== currentFullId) {
            console.log("✏️ [CreateCollectionDialog] Setting user edited flag (different from auto-generated)");
            setUserEditedId(true);
        } else {
            console.log("✏️ [CreateCollectionDialog] Clearing user edited flag (matches auto-generated)");
            setUserEditedId(false);
        }
    };

    const onSubmit = async (values: z.infer<typeof formSchema>) => {
        console.log("🚀 [CreateCollectionDialog] Form submitted with values:", values);

        try {
            setIsSubmitting(true);
            console.log("⏳ [CreateCollectionDialog] Setting isSubmitting to true");

            // Step 1: Create the collection first
            console.log("📝 [CreateCollectionDialog] Creating collection");
            const payload = {
                name: values.name,
                readable_id: values.readable_id || undefined, // If empty, backend will generate one
            };
            console.log("📤 [CreateCollectionDialog] Request payload:", payload);

            const collectionResponse = await apiClient.post("/collections/", payload);

            if (!collectionResponse.ok) {
                const errorText = await collectionResponse.text();
                console.error("❌ [CreateCollectionDialog] Failed to create collection:", errorText);
                throw new Error(`Failed to create collection: ${errorText}`);
            }

            const collection = await collectionResponse.json();
            const collectionId = collection.readable_id;
            console.log("✅ [CreateCollectionDialog] Collection created successfully:", collection);

            toast.success("Collection created successfully");
            setCreatedCollectionId(collectionId);

            // Step 2: Initiate source connection using our new ConnectToSourceFlow logic
            console.log("🔌 [CreateCollectionDialog] Initiating connection to source");
            await initiateConnection(
                sourceShortName,
                sourceName,
                collectionId,
                sourceDetails,
                () => {
                    // Only close the dialog after the config is complete
                    console.log("🪟 [CreateCollectionDialog] Now closing dialog after config complete");
                    onClose();
                }
            );
            console.log("🔄 [CreateCollectionDialog] Connection initiation started");

        } catch (error) {
            console.error("❌ [CreateCollectionDialog] Error in submission:", error);
            toast.error(error instanceof Error ? error.message : "Failed to create collection");
        } finally {
            setIsSubmitting(false);
            console.log("⏳ [CreateCollectionDialog] Setting isSubmitting to false");
        }
    };

    // Determine appropriate message text based on source details
    const getInfoMessage = () => {
        if (sourceDetails?.auth_fields?.fields) {
            return `After creating this collection, you'll need to provide additional configuration for ${sourceName}.`;
        } else if (sourceDetails?.auth_type?.startsWith("oauth2")) {
            return `After creating this collection, you'll be redirected to authenticate with ${sourceName}.`;
        } else {
            return `After creating this collection, it will be automatically connected to ${sourceName}.`;
        }
    };

    console.log("🔄 [CreateCollectionDialog] Rendering dialog with state:", {
        isOpen,
        isSubmitting,
        isCheckingSource,
        nameValue,
        readableIdValue,
        userEditedId,
        hasSourceDetails: !!sourceDetails
    });

    return (
        <>
            <Dialog open={isOpen} onOpenChange={(open) => {
                console.log("🪟 [CreateCollectionDialog] Dialog open state changing to:", open);
                if (!open) onClose();
            }}>
                <DialogPortal>
                    <DialogOverlay className="bg-black/75" />
                    <div className="fixed inset-0 z-50 flex items-center justify-center">
                        <div className={cn(
                            "w-[600px] p-8 max-w-[90vw] max-h-[90vh] overflow-auto rounded-xl border",
                            isDark
                                ? "bg-background border-gray-800"
                                : "bg-background border-gray-200"
                        )}>
                            {/* Heading */}
                            <h1 className="text-4xl font-semibold text-left mb-10">
                                Create collection
                            </h1>

                            {/* Source Icon */}
                            <div className="flex justify-center mb-16">
                                <div className={cn(
                                    "w-36 h-36 flex items-center justify-center border border-black rounded-lg p-2",
                                    isDark ? "border-gray-700" : "border-gray-800"
                                )}>
                                    <img
                                        src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                        alt={`${sourceName} icon`}
                                        className="w-full h-full object-contain"
                                        onError={(e) => {
                                            console.log("🖼️ [CreateCollectionDialog] Image error, using fallback");
                                            e.currentTarget.style.display = 'none';
                                            e.currentTarget.parentElement!.innerHTML = `
                                                <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'
                                                }">
                                                    <span class="text-4xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'
                                                }">
                                                        ${sourceShortName.substring(0, 2).toUpperCase()}
                                                    </span>
                                                </div>
                                            `;
                                        }}
                                    />
                                </div>
                            </div>

                            {/* Form */}
                            <form onSubmit={(e) => {
                                console.log("📝 [CreateCollectionDialog] Form submit event triggered");
                                form.handleSubmit(onSubmit)(e);
                            }} className="space-y-4">
                                {/* Name field */}
                                <div className="space-y-1">
                                    <label className="text-sm font-medium ml-1">name</label>
                                    <div className="relative">
                                        <input
                                            type="text"
                                            className={cn(
                                                "w-full py-2 px-3 rounded-md border bg-transparent pr-10",
                                                isDark
                                                    ? "border-gray-700 focus:border-blue-500"
                                                    : "border-gray-300 focus:border-blue-500",
                                                "focus:outline-none"
                                            )}
                                            value={nameValue}
                                            onChange={handleNameChange}
                                            placeholder="My Collection"
                                        />
                                        <Pencil className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground opacity-70" />
                                    </div>
                                    {form.formState.errors.name && (
                                        <p className="text-sm text-red-500 mt-1">
                                            {form.formState.errors.name.message}
                                        </p>
                                    )}
                                </div>

                                {/* Readable ID field */}
                                <div className="space-y-1">
                                    <label className="text-sm font-medium ml-1">readable id</label>
                                    <div className="relative">
                                        <input
                                            type="text"
                                            className={cn(
                                                "w-full py-2 px-3 rounded-md border bg-transparent pr-10",
                                                isDark
                                                    ? "border-gray-700 focus:border-blue-500"
                                                    : "border-gray-300 focus:border-blue-500",
                                                "focus:outline-none"
                                            )}
                                            value={readableIdValue}
                                            onChange={handleReadableIdChange}
                                            placeholder="Auto-generated"
                                        />
                                        <Pencil className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground opacity-70" />
                                    </div>
                                    {form.formState.errors.readable_id && (
                                        <p className="text-sm text-red-500 mt-1">
                                            {form.formState.errors.readable_id.message}
                                        </p>
                                    )}
                                </div>

                                {/* Message about next steps */}
                                <div className={cn(
                                    "flex items-start space-x-2 rounded-md border p-3 mt-3",
                                    isDark
                                        ? "bg-blue-900/30 border-blue-800 text-blue-300"
                                        : "bg-blue-50 border-blue-200 text-blue-800"
                                )}>
                                    <Info size={18} className={cn(
                                        "mt-0.5",
                                        isDark ? "text-blue-400" : "text-blue-500"
                                    )} />
                                    <div className="text-sm">
                                        {getInfoMessage()}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex justify-end gap-3 pt-0">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => {
                                            console.log("🔄 [CreateCollectionDialog] Cancel button clicked");
                                            onClose();
                                        }}
                                        className={cn(
                                            "px-6",
                                            isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                                        )}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        type="submit"
                                        disabled={isSubmitting || isCheckingSource}
                                        className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                                        onClick={() => {
                                            console.log("🔄 [CreateCollectionDialog] Create button clicked");
                                        }}
                                    >
                                        {isSubmitting || isCheckingSource ? (
                                            <>
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Creating...
                                            </>
                                        ) : (
                                            "Create"
                                        )}
                                    </Button>
                                </div>
                            </form>
                        </div>
                    </div>
                </DialogPortal>
            </Dialog>

            {/* Render config dialog if needed */}
            {renderConfigDialog()}
        </>
    );
};

export default CreateCollectionDialog;
