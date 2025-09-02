import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox } from "@/search/SearchBox";
import { SearchResponseDisplay } from "@/search/SearchResponseDisplay";
import { SearchProcess } from "@/search/SearchProcess";

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

    // Search response state (final)
    const [searchResponse, setSearchResponse] = useState<any>(null);
    const [responseTime, setResponseTime] = useState<number | null>(null);
    const [searchResponseType, setSearchResponseType] = useState<'raw' | 'completion'>('raw');

    // Streaming lifecycle state (Milestone 1)
    const [showProcessPanel, setShowProcessPanel] = useState<boolean>(false);
    const [showResponsePanel, setShowResponsePanel] = useState<boolean>(false);

    const [requestId, setRequestId] = useState<string | null>(null);
    const [events, setEvents] = useState<any[]>([]);

    // streaming completion tokens
    const [streamingCompletion, setStreamingCompletion] = useState<string>("");
    // final results
    const [liveResults, setLiveResults] = useState<any[]>([]);

    // search state
    const [isCancelling, setIsCancelling] = useState<boolean>(false);
    const [isSearching, setIsSearching] = useState(false);

    // Handle search results from SearchBox
    const handleSearchResult = useCallback((response: any, responseType: 'raw' | 'completion', responseTimeMs: number) => {
        console.log('[CollectionNewView] handleSearchResult called:', {
            response,
            responseType,
            responseTimeMs,
            hasCompletion: !!response?.completion,
            completionLength: response?.completion?.length,
            currentStreamingCompletion: streamingCompletion?.length,
            currentIsSearching: isSearching
        });
        setSearchResponse(response);
        setSearchResponseType(responseType);
        setResponseTime(responseTimeMs);

        // Log the state after setting
        console.log('[CollectionNewView] handleSearchResult - state will be:', {
            searchResponse: response,
            searchResponseType: responseType,
            isSearching: isSearching // Note: this might still be true when this is called
        });
    }, [streamingCompletion, isSearching]);

    const handleSearchStart = useCallback((responseType: 'raw' | 'completion') => {
        console.log('[CollectionNewView] handleSearchStart called with responseType:', responseType);
        // Open panels on first search
        if (!showProcessPanel) setShowProcessPanel(true);
        if (!showResponsePanel) setShowResponsePanel(true);

        // Reset per-search state
        setIsSearching(true);
        setIsCancelling(false);
        setSearchResponse(null);
        setResponseTime(null);
        setSearchResponseType(responseType);  // Set the response type for this search
        setEvents([]);
        setStreamingCompletion("");
        setLiveResults([]);
        setRequestId(null);
    }, [showProcessPanel, showResponsePanel]);

    const handleSearchEnd = useCallback(() => {
        console.log('[CollectionNewView] handleSearchEnd called');

        setIsSearching(false);
        setIsCancelling(false);

        // Don't hide the panel here - the panel visibility should be determined by
        // whether we have content to show, not by stale closure values
        // The issue was that this callback was capturing initial null/empty values
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
                "mx-auto py-6 px-4 sm:px-6 md:px-8 w-full md:w-[80%] lg:w-[70%] xl:w-[70%]",
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
                    onStreamEvent={(event: any) => {
                        setEvents(prev => [...prev, event]);
                        if (event?.type === 'connected' && event.request_id) {
                            setRequestId(event.request_id as string);
                        }
                    }}
                    onStreamUpdate={(partial: any) => {
                        if (partial && Object.prototype.hasOwnProperty.call(partial, 'requestId')) {
                            setRequestId(partial.requestId ?? null);
                        }
                        if (typeof partial?.streamingCompletion === 'string') {
                            setStreamingCompletion(partial.streamingCompletion);
                        }
                        if (Array.isArray(partial?.results)) {
                            setLiveResults(partial.results);
                        }
                    }}
                />
            </div>

            {/* Live Process timeline */}
            {showProcessPanel && (
                <div className="mt-4">
                    <SearchProcess requestId={requestId} events={events as any[]} />
                </div>
            )}

            {/* Search Response Display - visibility controlled by panel state (Milestone 1) */}
            {showResponsePanel && (
                <div className="mt-6">
                    <SearchResponseDisplay
                        searchResponse={(() => {
                            const response = isSearching
                                ? { status: 'in_progress', completion: streamingCompletion, results: liveResults }
                                : searchResponse;

                            console.log('[CollectionNewView] Passing to SearchResponseDisplay:', {
                                isSearching,
                                responseType: searchResponseType,
                                whichResponse: isSearching ? 'STREAMING (temporary object)' : 'FINAL (from handleSearchResult)',
                                streamingCompletion: isSearching ? streamingCompletion?.substring(0, 50) + '...' : 'N/A',
                                finalResponse: !isSearching ? searchResponse : 'N/A',
                                responseObject: response
                            });

                            return response;
                        })()}
                        isSearching={isSearching}
                        responseType={searchResponseType}
                    />
                </div>
            )}
        </div>
    );
};

export default CollectionNewView;
