import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox } from "@/search/SearchBox";
import { SearchResponseDisplay } from "@/search/SearchResponseDisplay";

/**
 * CollectionNewView Component
 *
 * The main search page for a collection, providing:
 * - SearchBox for query input and configuration
 * - SearchResponseDisplay for showing results
 * - Clean separation of concerns for maintainability
 */
const CollectionNewView = () => {
    const { readable_id } = useParams();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Search response state
    const [searchResponse, setSearchResponse] = useState<any>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [responseTime, setResponseTime] = useState<number | null>(null);
    const [searchResponseType, setSearchResponseType] = useState<'raw' | 'completion'>('raw');

    // Handle search results from SearchBox
    const handleSearchResult = useCallback((response: any, responseType: 'raw' | 'completion', responseTimeMs: number) => {
        setSearchResponse(response);
        setSearchResponseType(responseType);
        setResponseTime(responseTimeMs);
    }, []);

    const handleSearchStart = useCallback(() => {
        setIsSearching(true);
        setSearchResponse(null);
        setResponseTime(null);
    }, []);

    const handleSearchEnd = useCallback(() => {
        setIsSearching(false);
    }, []);

    if (!readable_id) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">No collection ID provided</p>
            </div>
        );
    }

    return (
        <div
            className={cn(
                // Reduce page width to ~60% on large screens, full width on small
                "mx-auto py-6 px-4 sm:px-6 md:px-8 w-full md:w-[80%] lg:w-[50%] xl:w-[45%]",
                isDark ? "text-foreground" : ""
            )}
        >
            {/* Collection header */}
            <div className="flex items-center justify-between py-2">
                <div>
                    <p className="text-muted-foreground text-sm mt-1">{readable_id}</p>
                </div>
            </div>

            {/* Search Box Component */}
            <div className="mt-6">
                <SearchBox
                    collectionId={readable_id}
                    onSearch={handleSearchResult}
                    onSearchStart={handleSearchStart}
                    onSearchEnd={handleSearchEnd}
                />
            </div>

            {/* Search Response Display */}
            {(searchResponse || isSearching) && (
                <div className="mt-6">
                    <SearchResponseDisplay
                        searchResponse={searchResponse}
                        isSearching={isSearching}
                        responseType={searchResponseType}
                    />
                </div>
            )}
        </div>
    );
};

export default CollectionNewView;
