import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { Loader2, Plus, Search } from "lucide-react";

// Import base components
import {
    Dialog,
    DialogContent,
    DialogPortal,
    DialogOverlay,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Source {
    id: string;
    name: string;
    description?: string | null;
    short_name: string;
    labels?: string[];
}

interface AddSourceConnectionDialogProps {
    isOpen: boolean;
    onClose: () => void;
    collectionId: string;
    collectionName: string;
}

export const AddSourceConnectionDialog: React.FC<AddSourceConnectionDialogProps> = ({
    isOpen,
    onClose,
    collectionId,
    collectionName,
}) => {
    const [sources, setSources] = useState<Source[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Fetch available sources
    useEffect(() => {
        const fetchSources = async () => {
            if (!isOpen) return;

            setIsLoading(true);
            setError(null);

            try {
                const response = await apiClient.get("/sources/list");
                if (response.ok) {
                    const data = await response.json();
                    setSources(data);
                } else {
                    setError("Failed to load sources");
                }
            } catch (err) {
                setError("An error occurred while fetching sources");
                console.error("Error fetching sources:", err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchSources();
    }, [isOpen]);

    // Handle source selection
    const handleSourceSelect = async (source: Source) => {
        setIsSubmitting(true);

        try {
            // Dummy API call - replace with real implementation later
            const payload = {
                collection: collectionId,
                source_id: source.id,
                name: `${collectionName} - ${source.name}`,
                short_name: source.short_name
            };

            // Mock successful API call
            await new Promise(resolve => setTimeout(resolve, 1000));

            toast({
                title: "Success",
                description: `Added ${source.name} connection to collection`
            });

            onClose();
            // Reload data would be handled by the parent component
        } catch (err) {
            toast({
                title: "Error",
                description: "Failed to add source connection",
                variant: "destructive"
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Filter sources based on search query
    const filteredSources = searchQuery
        ? sources.filter(source =>
            source.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            source.short_name.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : sources;

    // Get color class based on shortName for fallback icons
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
        <Dialog open={isOpen} onOpenChange={(open) => {
            if (!open) onClose();
        }}>
            <DialogPortal>
                <DialogOverlay className="bg-black/75" />
                <DialogContent
                    className={cn(
                        "flex flex-col w-[700px] h-[600px] p-0 max-w-[90vw] max-h-[90vh] rounded-xl border",
                        isDark ? "bg-background border-gray-800" : "bg-background border-gray-200"
                    )}
                >
                    {/* Heading and Search - Fixed section */}
                    <div className="p-8 pb-4 flex-shrink-0">
                        <DialogTitle className="text-2xl font-semibold text-left">
                            Add source connection to "{collectionName}"
                        </DialogTitle>
                        <DialogDescription className="text-sm text-muted-foreground mt-1">
                            <span className="font-mono">{collectionId}</span>
                        </DialogDescription>

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
                    <div className="flex-grow overflow-y-auto px-8 pb-4">
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center py-12">
                                <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
                                <p className="text-muted-foreground">Loading available sources...</p>
                            </div>
                        ) : error ? (
                            <div className="text-center py-8 text-red-500">
                                <p>{error}</p>
                                <Button
                                    onClick={() => window.location.reload()}
                                    variant="outline"
                                    className="mt-2"
                                >
                                    Retry
                                </Button>
                            </div>
                        ) : (
                            <>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {filteredSources.map((source) => (
                                        <div
                                            key={source.id}
                                            className={cn(
                                                "border rounded-lg overflow-hidden cursor-pointer group transition-all",
                                                isDark
                                                    ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900"
                                                    : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50"
                                            )}
                                            onClick={() => !isSubmitting && handleSourceSelect(source)}
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
                                                    <span className="text-sm font-medium truncate max-w-[180px]">{source.name}</span>
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
                                                    disabled={isSubmitting}
                                                >
                                                    <Plus className="h-4 w-4 group-hover:h-5 group-hover:w-5 transition-all" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {filteredSources.length === 0 && (
                                    <div className="text-center py-8 text-muted-foreground">
                                        <p>No sources found matching your search.</p>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    {/* Footer - Fixed height */}
                    <DialogFooter className="p-8 pt-4 border-t flex-shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                            className={cn(
                                "px-6",
                                isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                            )}
                        >
                            Cancel
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </DialogPortal>
        </Dialog>
    );
};

export default AddSourceConnectionDialog;
