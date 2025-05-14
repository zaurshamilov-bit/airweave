/**
 * SourceSelectorView.tsx
 *
 * This component displays a grid of available data sources that users can select
 * to connect to their collection. It's a key entry point in the ConnectFlow dialog
 * when starting from the "add source" mode.
 *
 * Key responsibilities:
 * 1. Fetch and display available data sources
 * 2. Allow filtering/searching of sources
 * 3. Handle source selection
 * 4. Pass selected source to the next step in the flow
 *
 * Flow context:
 * - Appears as the first step when adding a source to an existing collection
 * - On selection, typically leads to CreateCollectionView
 * - Can handle pre-selected sources from props
 */

import { useState, useEffect } from "react";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Plus, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { DialogViewProps } from "../FlowDialog";
import { getAppIconUrl } from "@/lib/utils/icons";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";

/**
 * Interface for source data from API
 */
interface Source {
    /** Unique identifier */
    id: string;
    /** Display name */
    name: string;
    /** Optional description */
    description?: string | null;
    /** Short name identifier (e.g., "github", "notion") */
    short_name: string;
    /** Optional categorization labels */
    labels?: string[];
}

/**
 * Props for the SourceSelectorView component
 * Extends FlowDialog's common DialogViewProps
 */
export interface SourceSelectorViewProps extends DialogViewProps {
    viewData?: {
        /** ID of existing collection when adding a source */
        collectionId?: string;
        /** Name of existing collection when adding a source */
        collectionName?: string;
        /** Optional pre-selected source ID */
        preselectedSourceId?: string;
        /** Flag indicating if we're creating a new collection (source-first flow) */
        isNewCollection?: boolean;
    };
}

/**
 * SourceSelectorView Component
 *
 * Grid display of available data sources with search functionality.
 * Allows selection of a source to connect to a collection.
 */
export const SourceSelectorView: React.FC<SourceSelectorViewProps> = ({
    onNext,
    onCancel,
    onComplete,
    viewData = {},
}) => {
    /** List of available sources from API */
    const [sources, setSources] = useState<Source[]>([]);
    /** Loading state during API fetch */
    const [isLoading, setIsLoading] = useState(true);
    /** Error message if source fetch fails */
    const [error, setError] = useState<string | null>(null);
    /** Search query for filtering sources */
    const [searchQuery, setSearchQuery] = useState("");
    /** For navigation */
    const navigate = useNavigate();

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { collectionId, collectionName, preselectedSourceId, isNewCollection } = viewData;

    /**
     * Handle errors by redirecting to dashboard with error parameters
     *
     * @param error - The error that occurred
     * @param errorType - Type of error for better context
     */
    const handleError = (error: Error | string, errorType: string) => {
        console.error(`❌ [SourceSelectorView] ${errorType}:`, error);

        // Create the service name with collection info if available
        const service = collectionId && collectionName ?
            `Collection: ${collectionName}` : undefined;

        // Use the common error utility to redirect
        redirectWithError(navigate, error, service);
    };

    /**
     * Fetch available sources from API
     * Handles auto-selection of preselected source if provided
     */
    useEffect(() => {
        const fetchSources = async () => {
            setIsLoading(true);
            setError(null);

            try {
                const response = await apiClient.get("/sources/list");
                if (response.ok) {
                    const data = await response.json();
                    setSources(data);

                    // If a source is preselected and it exists in the data, auto-select it
                    if (preselectedSourceId) {
                        const selectedSource = data.find((source: Source) => source.id === preselectedSourceId);
                        if (selectedSource) {
                            handleSourceSelect(selectedSource);
                        }
                    }
                } else {
                    const errorText = await response.text();
                    throw new Error(`Failed to load sources: ${errorText}`);
                }
            } catch (err) {
                console.error("Error fetching sources:", err);
                handleError(err instanceof Error ? err : new Error(String(err)), "Failed to fetch sources");
            } finally {
                setIsLoading(false);
            }
        };

        fetchSources();
    }, [preselectedSourceId]);

    /**
     * Handle source selection
     * Proceeds to appropriate next step based on context
     *
     * @param source The selected source
     */
    const handleSourceSelect = (source: Source) => {
        console.log(`Selected source: ${source.name} (${source.short_name})`);

        // If we're creating a new collection (source-first flow)
        if (isNewCollection) {
            console.log("🔄 [SourceSelectorView] In source-first-collection mode, proceeding to collection creation");
            onNext?.({
                view: 'createCollection',
                data: {
                    sourceId: source.id,
                    sourceName: source.name,
                    sourceShortName: source.short_name
                }
            });
        }
        // If collection ID is available, move to source config with collection info
        else if (collectionId) {
            onNext?.({
                view: 'sourceConfig',
                data: {
                    sourceId: source.id,
                    sourceName: source.name,
                    sourceShortName: source.short_name,
                    collectionId
                }
            });
        } else {
            // Otherwise, move to create collection with source info
            onNext?.({
                view: 'createCollection',
                data: {
                    sourceId: source.id,
                    sourceName: source.name,
                    sourceShortName: source.short_name
                }
            });
        }
    };

    /**
     * Filter sources based on search query
     * Matches on name or short_name (case insensitive)
     */
    const filteredSources = searchQuery
        ? sources.filter(source =>
            source.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            source.short_name.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : sources;

    /**
     * Generate a consistent color for source icons
     * Uses the source short name to deterministically select a color
     *
     * @param shortName Source short name
     * @returns CSS color class
     */
    const getColorClass = (shortName: string) => {
        const colors = [
            "bg-blue-500",
            "bg-green-500",
            "bg-purple-500",
            "bg-orange-500",
            "bg-pink-500",
            "bg-indigo-500",
            "bg-red-500",
            "bg-yellow-500",
        ];

        // Hash the short name to get a consistent color
        const index = shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
        return colors[index];
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header section - fixed */}
            <div className="flex-shrink-0 p-8 pb-4">
                <DialogTitle className="text-2xl font-semibold text-left">
                    {isNewCollection
                        ? "Choose a first source for your new collection"
                        : collectionId
                            ? `Add source connection to "${collectionName || collectionId}"`
                            : "Select a source to connect"}
                </DialogTitle>
                {collectionId && (
                    <DialogDescription className="text-sm text-muted-foreground mt-1">
                        <span className="font-mono">{collectionId}</span>
                    </DialogDescription>
                )}

                {/* Search */}
                <div className="relative mt-6 mb-2">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        className="pl-10"
                        placeholder="Search sources..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {/* Sources Grid - Scrollable section */}
            <div className="flex-grow overflow-y-auto p-8 pt-2">
                {isLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
                        <p className="text-muted-foreground">Loading available sources...</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-3">
                        {filteredSources.map((source) => (
                            <div
                                key={source.id}
                                className={cn(
                                    "border rounded-lg overflow-hidden cursor-pointer group transition-all my-1.5",
                                    isDark
                                        ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900"
                                        : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50"
                                )}
                                onClick={() => handleSourceSelect(source)}
                            >
                                <div className="p-4 flex items-center justify-between">
                                    <div className="flex items-center gap-3 min-w-0 flex-1 mr-2">
                                        <div className="flex items-center justify-center w-10 h-10 overflow-hidden rounded-md flex-shrink-0">
                                            <img
                                                src={getAppIconUrl(source.short_name, resolvedTheme)}
                                                alt={`${source.short_name} icon`}
                                                className="w-9 h-9 object-contain"
                                                onError={(e) => {
                                                    e.currentTarget.style.display = 'none';
                                                    e.currentTarget.parentElement!.classList.add(getColorClass(source.short_name));
                                                    e.currentTarget.parentElement!.innerHTML = `<span class="text-white font-semibold text-sm">${source.short_name.substring(0, 2).toUpperCase()}</span>`;
                                                }}
                                            />
                                        </div>
                                        <span className="text-sm font-medium truncate max-w-[100px]">{source.name}</span>
                                    </div>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className={cn(
                                            "h-8 w-8 rounded-full flex-shrink-0",
                                            isDark
                                                ? "bg-gray-800/80 text-blue-400 hover:bg-blue-600/20 hover:text-blue-300 group-hover:bg-blue-600/30"
                                                : "bg-gray-100/80 text-blue-500 hover:bg-blue-100 hover:text-blue-600 group-hover:bg-blue-100/80"
                                        )}
                                    >
                                        <Plus className="h-4 w-4 group-hover:h-5 group-hover:w-5 transition-all" />
                                    </Button>
                                </div>
                            </div>
                        ))}

                        {filteredSources.length === 0 && (
                            <div className="col-span-2 text-center py-8 text-muted-foreground">
                                <p>No sources found matching your search.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Footer - Fixed section */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="p-6">
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
                </DialogFooter>
            </div>
        </div>
    );
};

export default SourceSelectorView;
