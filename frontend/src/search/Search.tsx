import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox } from "@/search/SearchBox";
import { SearchResponse } from "@/search/SearchResponse";
import { SearchProcess } from "@/search/SearchProcess";
import { DESIGN_SYSTEM } from "@/lib/design-system";

interface SearchProps {
    collectionReadableId: string;
}

/**
 * Search Component
 *
 * The main search component for a collection, providing:
 * - SearchBox for query input and configuration
 * - SearchResponseDisplay for showing results
 * - Clean separation of concerns for maintainability
 */
export const Search = ({ collectionReadableId }: SearchProps) => {
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

    return (
        <div
            className={cn(
                "w-full max-w-[1000px]",
                DESIGN_SYSTEM.spacing.margins.section,
                isDark ? "text-foreground" : ""
            )}
        >
            {/* Search Box Component */}
            <div>
                <SearchBox
                    collectionId={collectionReadableId}
                    onSearch={handleSearchResult}
                    onSearchStart={handleSearchStart}
                    onSearchEnd={handleSearchEnd}
                    onCancel={() => {
                        console.log('[CollectionNewView] onCancel received');
                        setIsCancelling(true);
                        // If we don’t yet have a final response, expose a cancelled placeholder
                        setSearchResponse((prev) => {
                            const next = prev || { results: [], completion: null, status: 'cancelled' };
                            console.log('[CollectionNewView] onCancel -> setting searchResponse', { prev, next });
                            return next;
                        });
                        setSearchResponseType((prev) => {
                            console.log('[CollectionNewView] onCancel -> responseType remains', prev);
                            return prev;
                        });
                        setIsSearching(false);
                    }}
                    onStreamEvent={(event: any) => {
                        setEvents(prev => [...prev, event]);
                        if (event?.type === 'cancelled') {
                            console.log('[CollectionNewView] Stream event: cancelled');
                        }
                        if (event?.type === 'connected' && event.request_id) {
                            setRequestId(event.request_id as string);
                        }
                    }}
                    onStreamUpdate={(partial: any) => {
                        console.log('[CollectionNewView] onStreamUpdate', partial);
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
                <div>
                    <SearchProcess
                        requestId={requestId}
                        events={events as any[]}
                        isSearching={isSearching}
                    />
                </div>
            )}

            {/* Search Response Display - visibility controlled by panel state (Milestone 1) */}
            {showResponsePanel && (
                <div>
                    <SearchResponse
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
