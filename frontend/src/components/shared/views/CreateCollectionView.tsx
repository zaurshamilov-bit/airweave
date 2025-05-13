import React, { useState, useRef, useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Pencil, Info, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import {
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { DialogViewProps } from "../FlowDialog";
import { getAppIconUrl } from "@/lib/utils/icons";

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

// Form schema validation with Zod
const formSchema = z.object({
    name: z.string().min(4, "Name must be at least 4 characters").max(64, "Name must be less than 64 characters"),
    readable_id: z.string().optional().refine(
        (val) => !val || /^[a-z0-9-]+$/.test(val),
        { message: "Readable ID must contain only lowercase letters, numbers, and hyphens" }
    ),
});

export interface CreateCollectionViewProps extends DialogViewProps {
    viewData?: {
        sourceName?: string;
        sourceShortName?: string;
        sourceId?: string;
    };
}

export const CreateCollectionView: React.FC<CreateCollectionViewProps> = ({
    onNext,
    onCancel,
    onComplete,
    viewData = {},
}) => {
    const { sourceName, sourceShortName, sourceId } = viewData;
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    const [isSubmitting, setIsSubmitting] = useState(false);
    const defaultCollectionName = sourceName ? `My ${sourceName} Collection` : "My Collection";

    // Use a ref to store the random suffix, so it persists across renders
    const randomSuffixRef = useRef(generateRandomSuffix());
    const previousNameRef = useRef(defaultCollectionName);
    const [userEditedId, setUserEditedId] = useState(false);

    // Directly manage input values to avoid the one-keypress delay
    const [nameValue, setNameValue] = useState(defaultCollectionName);
    const [readableIdValue, setReadableIdValue] = useState("");

    // Initialize form with react-hook-form
    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            name: defaultCollectionName,
            readable_id: getReadableId(defaultCollectionName),
        },
    });

    // Reset form when dialog opens with default values
    useEffect(() => {
        // Generate a new random suffix
        randomSuffixRef.current = generateRandomSuffix();

        previousNameRef.current = defaultCollectionName;
        setNameValue(defaultCollectionName);
        const generatedId = getReadableId(defaultCollectionName);
        setReadableIdValue(generatedId);

        form.reset({
            name: defaultCollectionName,
            readable_id: generatedId,
        });

        setUserEditedId(false);
    }, [defaultCollectionName, form]);

    // Get the base readable ID from the name
    function getReadableId(name: string) {
        // If name is empty or just whitespace, return empty string
        if (!name || name.trim() === "") {
            return "";
        }

        const base = generateReadableIdBase(name);
        return base ? `${base}-${randomSuffixRef.current}` : "";
    }

    // Handle name change - immediate update for both name and readable_id
    const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newName = e.target.value;

        setNameValue(newName);
        form.setValue("name", newName);

        // If the field was cleared, generate a new suffix for a fresh start
        if (previousNameRef.current && newName === "" && !userEditedId) {
            randomSuffixRef.current = generateRandomSuffix();
        }

        // Only auto-generate if user hasn't manually edited it
        if (!userEditedId) {
            // If name is empty, set readable_id to empty as well
            if (!newName || newName.trim() === "") {
                const emptyId = "";
                setReadableIdValue(emptyId);
                form.setValue("readable_id", emptyId);
            } else {
                const newId = getReadableId(newName);
                setReadableIdValue(newId);
                form.setValue("readable_id", newId);
            }
        }

        // Update previous name reference
        previousNameRef.current = newName;
    };

    // Handle readable ID change
    const handleReadableIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newId = e.target.value;

        setReadableIdValue(newId);
        form.setValue("readable_id", newId);

        // If name is empty, always allow editing the ID
        if (!nameValue || nameValue.trim() === "") {
            setUserEditedId(true);
            return;
        }

        const currentNameBase = generateReadableIdBase(nameValue);
        const currentFullId = `${currentNameBase}-${randomSuffixRef.current}`;

        // If value is different from auto-generated, user has edited it
        if (newId !== currentFullId) {
            setUserEditedId(true);
        } else {
            setUserEditedId(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            setIsSubmitting(true);

            // Validate the form
            const values = await form.trigger();
            if (!form.formState.isValid) return;

            // Get the values
            const collectionDetails = {
                name: nameValue,
                readable_id: readableIdValue || undefined,
            };

            // If sourceId and sourceShortName are provided, continue to source config
            if (sourceId && sourceShortName) {
                // Pass data to the next view (SourceConfigView)
                onNext?.({
                    view: 'sourceConfig',
                    data: {
                        collectionDetails,
                        sourceId,
                        sourceName,
                        sourceShortName
                    }
                });
            } else {
                // Complete the flow with collection details
                onComplete?.(collectionDetails);
            }
        } catch (error) {
            console.error("Error in collection creation:", error);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 h-full flex flex-col">
                    {/* Heading */}
                    <DialogTitle className="text-4xl font-semibold text-left mb-8">
                        Create collection
                    </DialogTitle>

                    {/* Small spacer to push emblem down 10% */}
                    <div style={{ height: "5%" }}></div>

                    {/* Source Icon (if applicable) - make much larger */}
                    {sourceShortName && (
                        <div className="flex justify-center items-center mb-6" style={{ minHeight: "20%" }}>
                            <div className={cn(
                                "w-64 h-64 flex items-center justify-center border border-black rounded-lg p-2",
                                isDark ? "border-gray-700" : "border-gray-800"
                            )}>
                                <img
                                    src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                    alt={`${sourceName} icon`}
                                    className="w-full h-full object-contain"
                                    onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        e.currentTarget.parentElement!.innerHTML = `
                        <div class="w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}">
                          <span class="text-5xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}">
                            ${sourceShortName.substring(0, 2).toUpperCase()}
                          </span>
                        </div>
                      `;
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Reduced spacer to bring form up closer to emblem */}
                    <div className="flex-grow" style={{ minHeight: "15%" }}></div>

                    {/* Form - positioned closer to emblem */}
                    <div className="px-2 max-w-md mx-auto pb-6">
                        <form onSubmit={handleSubmit} className="space-y-6">
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
                            {sourceShortName && (
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
                                    <DialogDescription className="text-sm">
                                        After creating this collection, you'll need to provide additional configuration for {sourceName}.
                                    </DialogDescription>
                                </div>
                            )}
                        </form>
                    </div>

                    {/* Small spacer at bottom */}
                    <div style={{ height: "5%" }}></div>
                </div>
            </div>

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-end gap-3 p-6">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={onCancel}
                        className={cn(
                            "px-6",
                            isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                        )}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={isSubmitting}
                        className="px-6 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Creating...
                            </>
                        ) : (
                            "Create"
                        )}
                    </Button>
                </DialogFooter>
            </div>
        </div>
    );
};

export default CreateCollectionView;
