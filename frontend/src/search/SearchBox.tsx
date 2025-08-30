import { useEffect, useState, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { Button } from "@/components/ui/button";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    ArrowUp,
    CodeXml,
    X,
    Loader2,
    Merge,
    ChevronsLeftRightEllipsis,
    RectangleEllipsis,
    Split,
    Filter,
    CalendarClock,
    ArrowUpWideNarrow,
    BrainCircuit
} from "lucide-react";
import { ApiIntegrationDoc } from "@/search/CodeBlock";
import { JsonFilterEditor } from "@/search/JsonFilterEditor";
import { RecencyBiasSlider } from "@/search/RecencyBiasSlider";
import { apiClient } from "@/lib/api";

// Search method types
type SearchMethod = "hybrid" | "neural" | "keyword";

// Toggle state interface
interface SearchToggles {
    queryExpansion: boolean;
    filter: boolean;
    queryInterpretation: boolean;
    recencyBias: boolean;
    reRanking: boolean;
    answer: boolean;
}

// Search configuration interface
export interface SearchConfig {
    search_method: SearchMethod;
    expansion_strategy: "auto" | "no_expansion";
    enable_query_interpretation: boolean;
    recency_bias: number | null;
    enable_reranking: boolean;
    response_type: "completion" | "raw";
    filter?: any;
}

// Component props
interface SearchBoxProps {
    collectionId: string;
    onSearch: (response: any, responseType: 'raw' | 'completion', responseTime: number) => void;
    onSearchStart?: () => void;
    onSearchEnd?: () => void;
    className?: string;
}

/**
 * SearchBox Component
 *
 * A comprehensive search interface component that handles:
 * - Query input with textarea
 * - Search method selection (hybrid/neural/keyword)
 * - Various search options with tooltips
 * - Filter configuration with JSON editor
 * - Recency bias slider
 * - API integration code modal
 * - Search execution and response handling
 */
export const SearchBox: React.FC<SearchBoxProps> = ({
    collectionId,
    onSearch,
    onSearchStart,
    onSearchEnd,
    className
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Core search state
    const [query, setQuery] = useState("");
    const [searchMethod, setSearchMethod] = useState<SearchMethod>("hybrid");
    const [isSearching, setIsSearching] = useState(false);

    // Filter state
    const [filterJson, setFilterJson] = useState("");
    const [isFilterValid, setIsFilterValid] = useState(true);

    // API key state
    const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");

    // Recency bias state
    const [recencyBiasValue, setRecencyBiasValue] = useState(0.0);

    // Code block modal state
    const [showCodeBlock, setShowCodeBlock] = useState(false);

    // Toggle buttons state
    const [toggles, setToggles] = useState<SearchToggles>({
        queryExpansion: true,
        filter: false,
        queryInterpretation: false,
        recencyBias: false,
        reRanking: true,
        answer: true
    });

    // Tooltip management state
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // Fetch API key on mount
    useEffect(() => {
        const fetchApiKey = async () => {
            try {
                const response = await apiClient.get("/api-keys");
                if (response.ok) {
                    const data = await response.json();
                    // Get the first API key if available
                    if (Array.isArray(data) && data.length > 0 && data[0].decrypted_key) {
                        setApiKey(data[0].decrypted_key);
                    }
                }
            } catch (err) {
                console.error("Error fetching API key:", err);
            }
        };

        fetchApiKey();
    }, []);

    // Handle escape key for modal
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && showCodeBlock) {
                setShowCodeBlock(false);
            }
        };

        if (showCodeBlock) {
            document.addEventListener('keydown', handleEscape);
            // Prevent body scroll when modal is open
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }

        // Cleanup
        return () => {
            if (tooltipTimeoutRef.current) {
                clearTimeout(tooltipTimeoutRef.current);
            }
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = '';
        };
    }, [showCodeBlock]);

    const hasQuery = query.trim().length > 0;

    // Main search handler
    const handleSendQuery = useCallback(async () => {
        if (!hasQuery || !collectionId || isSearching) return;

        setIsSearching(true);
        onSearchStart?.();

        const startTime = performance.now();

        // Store the response type being used for this search
        const currentResponseType = toggles.answer ? "completion" : "raw";

        try {
            // Parse filter if enabled and valid
            let parsedFilter = null;
            if (toggles.filter && filterJson && isFilterValid) {
                try {
                    parsedFilter = JSON.parse(filterJson);
                } catch (e) {
                    console.error("Failed to parse filter JSON:", e);
                    parsedFilter = null;
                }
            }

            // Build request body with all parameters
            const requestBody: any = {
                query: query,
                search_method: searchMethod,
                expansion_strategy: toggles.queryExpansion ? "auto" : "no_expansion",
                enable_query_interpretation: toggles.queryInterpretation,
                recency_bias: toggles.recencyBias ? recencyBiasValue : null,
                enable_reranking: toggles.reRanking,
                response_type: currentResponseType,
                score_threshold: null,
                limit: 20,
                offset: 0
            };

            // Add filter only if it's valid
            if (parsedFilter) {
                requestBody.filter = parsedFilter;
            }

            console.log("Sending search request:", requestBody);

            // Make the API call
            const response = await apiClient.post(
                `/collections/${collectionId}/search`,
                requestBody
            );

            const endTime = performance.now();
            const responseTime = Math.round(endTime - startTime);

            if (response.ok) {
                const data = await response.json();
                console.log("Search response:", data);
                onSearch(data, currentResponseType, responseTime);
            } else {
                // Handle error response
                const errorText = await response.text();
                let errorMessage = `Search failed: ${response.status} ${response.statusText}`;

                try {
                    const errorJson = JSON.parse(errorText);
                    if (errorJson.detail) {
                        errorMessage = errorJson.detail;
                    }
                } catch {
                    // If not JSON, use the text as-is
                    if (errorText) {
                        errorMessage = errorText;
                    }
                }

                console.error("Search error:", errorMessage);
                onSearch({ error: errorMessage, status: response.status }, currentResponseType, responseTime);
            }
        } catch (error) {
            const endTime = performance.now();
            const responseTime = Math.round(endTime - startTime);
            console.error("Search request failed:", error);
            onSearch({
                error: error instanceof Error ? error.message : "An unexpected error occurred",
                status: 0
            }, currentResponseType, responseTime);
        } finally {
            setIsSearching(false);
            onSearchEnd?.();
        }
    }, [hasQuery, collectionId, query, searchMethod, toggles, filterJson, isFilterValid, recencyBiasValue, isSearching, onSearch, onSearchStart, onSearchEnd]);

    // Handle search method change
    const handleMethodChange = useCallback((newMethod: SearchMethod) => {
        setSearchMethod(newMethod);
    }, []);

    // Handle toggle button clicks
    const handleToggle = useCallback((name: keyof SearchToggles, displayName: string) => {
        // Special handling for recency bias
        if (name === 'recencyBias') {
            // If turning off manually, keep the slider value
            setToggles(prev => ({
                ...prev,
                recencyBias: !prev.recencyBias
            }));
        } else {
            setToggles(prev => ({
                ...prev,
                [name]: !prev[name]
            }));
        }
    }, []);

    // Handle recency bias slider changes
    const handleRecencyBiasChange = useCallback((value: number) => {
        setRecencyBiasValue(value);
        // Auto-toggle on when value > 0, off when value = 0
        setToggles(prev => ({
            ...prev,
            recencyBias: value > 0
        }));
    }, []);

    // Tooltip management helpers
    const handleTooltipMouseEnter = useCallback((tooltipId: string) => {
        // Clear any pending timeout
        if (tooltipTimeoutRef.current) {
            clearTimeout(tooltipTimeoutRef.current);
            tooltipTimeoutRef.current = null;
        }
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipMouseLeave = useCallback((tooltipId: string) => {
        // Only close if we're not hovering over the tooltip content
        if (hoveredTooltipContent !== tooltipId) {
            // Add a small delay before closing to allow moving to tooltip content
            tooltipTimeoutRef.current = setTimeout(() => {
                setOpenTooltip(prev => prev === tooltipId ? null : prev);
            }, 100);
        }
    }, [hoveredTooltipContent]);

    const handleTooltipContentMouseEnter = useCallback((tooltipId: string) => {
        // Clear any pending timeout
        if (tooltipTimeoutRef.current) {
            clearTimeout(tooltipTimeoutRef.current);
            tooltipTimeoutRef.current = null;
        }
        setHoveredTooltipContent(tooltipId);
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipContentMouseLeave = useCallback((tooltipId: string) => {
        setHoveredTooltipContent(null);
        // Close the tooltip after a small delay
        tooltipTimeoutRef.current = setTimeout(() => {
            setOpenTooltip(prev => prev === tooltipId ? null : prev);
        }, 100);
    }, []);

    return (
        <>
            <div className={cn("w-full", className)}>
                <div
                    className={cn(
                        "rounded-2xl border overflow-hidden",
                        isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"
                    )}
                >
                    <div className="relative px-2 pt-2 pb-1">
                        {/* Code button - prominent with label */}
                        <button
                            type="button"
                            onClick={() => setShowCodeBlock(true)}
                            className={cn(
                                "absolute top-2 right-2 inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-white shadow-sm transition-colors",
                                "bg-sky-900 hover:bg-sky-700 ring-1 ring-sky-900/60"
                            )}
                            title="View integration code"
                        >
                            <CodeXml className="h-4 w-4" />
                            <span className="text-xs font-medium">Code</span>
                        </button>

                        <textarea
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    if (!hasQuery || isSearching) return;
                                    e.preventDefault();
                                    handleSendQuery();
                                }
                            }}
                            placeholder="Ask a question about your data"
                            className={cn(
                                // pr-16 ensures text wraps before overlay button
                                "w-full h-20 px-2 pr-16 py-1.5 text-sm leading-relaxed resize-none overflow-y-auto outline-none rounded-xl bg-transparent",
                                isDark ? "placeholder:text-gray-500" : "placeholder:text-gray-500"
                            )}
                        />
                    </div>
                    <div className={cn(
                        // Compact controls row
                        "flex items-center justify-between px-2 pb-2"
                    )}>
                        {/* Controlled tooltips for instant response */}
                        <TooltipProvider>
                            {/* Left side controls */}
                            <div className="flex items-center gap-1.5">
                                {/* 1. Method segmented control (icons) */}
                                <div className="h-8 inline-block">
                                    <div
                                        className={cn(
                                            "relative h-full",
                                            "rounded-md border p-0.5 gap-0.5 overflow-hidden",
                                            "grid grid-cols-3 items-stretch",
                                            isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                        )}
                                    >
                                        {/* HYBRID */}
                                        <Tooltip open={openTooltip === "hybrid"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "hybrid" ? undefined : () => handleMethodChange("hybrid")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("hybrid")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("hybrid")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center rounded transition-colors border",
                                                        searchMethod === "hybrid"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Hybrid search"
                                                >
                                                    <Merge className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={cn(
                                                    "max-w-[280px] p-2.5 rounded-md bg-gray-900 text-white",
                                                    "border border-white/10 shadow-lg text-xs"
                                                )}
                                                arrowClassName="fill-gray-900"
                                                onMouseEnter={() => handleTooltipContentMouseEnter("hybrid")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("hybrid")}
                                            >
                                                <div className="space-y-2">
                                                    <div className="text-sm font-semibold">Search method: Hybrid</div>
                                                    <p className="text-xs text-white/90">
                                                        Combines AI semantic and keyword signals for the best overall relevance.
                                                    </p>
                                                    <div className="pt-2 mt-2 border-t border-white/10">
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>

                                        {/* NEURAL */}
                                        <Tooltip open={openTooltip === "neural"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "neural" ? undefined : () => handleMethodChange("neural")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("neural")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("neural")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center rounded transition-colors border",
                                                        searchMethod === "neural"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Neural search"
                                                >
                                                    <ChevronsLeftRightEllipsis className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={cn(
                                                    "max-w-[280px] p-2.5 rounded-md bg-gray-900 text-white",
                                                    "border border-white/10 shadow-lg text-xs"
                                                )}
                                                arrowClassName="fill-gray-900"
                                                onMouseEnter={() => handleTooltipContentMouseEnter("neural")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("neural")}
                                            >
                                                <div className="space-y-2">
                                                    <div className="text-sm font-semibold">Search method: Neural</div>
                                                    <p className="text-xs text-white/90">
                                                        Pure semantic matching using transformer embeddings.
                                                    </p>
                                                    <div className="pt-2 mt-2 border-t border-white/10">
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>

                                        {/* KEYWORD */}
                                        <Tooltip open={openTooltip === "keyword"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "keyword" ? undefined : () => handleMethodChange("keyword")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("keyword")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("keyword")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center rounded transition-colors border",
                                                        searchMethod === "keyword"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Keyword search"
                                                >
                                                    <RectangleEllipsis className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={cn(
                                                    "max-w-[280px] p-2.5 rounded-md bg-gray-900 text-white",
                                                    "border border-white/10 shadow-lg text-xs"
                                                )}
                                                arrowClassName="fill-gray-900"
                                                onMouseEnter={() => handleTooltipContentMouseEnter("keyword")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("keyword")}
                                            >
                                                <div className="space-y-2">
                                                    <div className="text-sm font-semibold">Search method: Keyword</div>
                                                    <p className="text-xs text-white/90">
                                                        BM25 keyword matching for exact term precision.
                                                    </p>
                                                    <div className="pt-2 mt-2 border-t border-white/10">
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                </div>

                                {/* 2. Query expansion (icon) */}
                                <Tooltip open={openTooltip === "queryExpansion"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("queryExpansion")}
                                            onMouseLeave={() => handleTooltipMouseLeave("queryExpansion")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.queryExpansion ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("queryExpansion", "query expansion")}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.queryExpansion
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <Split className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "max-w-[220px] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("queryExpansion")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("queryExpansion")}
                                    >
                                        <div className="space-y-2">
                                            <div className="text-sm font-semibold">Query expansion</div>
                                            <p className="text-xs text-white/90">Generates similar versions of your query to improve recall.</p>
                                            <div className="pt-2 mt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#query-expansion"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 3. Filter */}
                                <Tooltip open={openTooltip === "filter"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("filter")}
                                            onMouseLeave={() => handleTooltipMouseLeave("filter")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.filter ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    handleToggle("filter", "filter");
                                                    // Keep tooltip open when enabling
                                                    if (!toggles.filter) {
                                                        setOpenTooltip("filter");
                                                    }
                                                }}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.filter
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <Filter className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "w-[360px] max-w-[90vw] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("filter")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("filter")}
                                    >
                                        <div className="space-y-3">
                                            <div>
                                                <div className="text-sm font-semibold">Metadata filtering</div>
                                                <p className="text-xs text-white/90 mt-1">Filter by fields like source, status, or date before searching.</p>
                                            </div>

                                            <div className="space-y-2">
                                                <div className="text-[11px] font-medium text-white/70">JSON:</div>
                                                <JsonFilterEditor
                                                    value={filterJson}
                                                    onChange={(value, isValid) => {
                                                        setFilterJson(value);
                                                        setIsFilterValid(isValid);
                                                    }}
                                                    height="160px"
                                                    className=""
                                                />
                                            </div>

                                            <div className="pt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#filtering-results"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 4. Query interpretation */}
                                <Tooltip open={openTooltip === "queryInterpretation"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("queryInterpretation")}
                                            onMouseLeave={() => handleTooltipMouseLeave("queryInterpretation")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.queryInterpretation ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("queryInterpretation", "query interpretation")}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.queryInterpretation
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <Filter className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "max-w-[220px] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("queryInterpretation")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("queryInterpretation")}
                                    >
                                        <div className="space-y-2">
                                            <div className="text-sm font-semibold">Query interpretation (beta)</div>
                                            <p className="text-xs text-white/90">Auto-extracts filters from natural language. May be over‑restrictive.</p>
                                            <div className="pt-2 mt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#query-interpretation-beta"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 5. Recency bias */}
                                <Tooltip open={openTooltip === "recencyBias"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("recencyBias")}
                                            onMouseLeave={() => handleTooltipMouseLeave("recencyBias")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.recencyBias ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    handleToggle("recencyBias", "recency bias");
                                                    // Open tooltip when enabling
                                                    if (!toggles.recencyBias) {
                                                        setOpenTooltip("recencyBias");
                                                    }
                                                }}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.recencyBias
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <CalendarClock className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "w-[240px] max-w-[90vw] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("recencyBias")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("recencyBias")}
                                    >
                                        <div className="space-y-2">
                                            <div className="text-sm font-semibold">Recency bias</div>
                                            <p className="text-xs text-white/90">Prioritize recent documents. Higher values give more weight to newer content.</p>
                                            <div className="pt-1 pb-1 px-1.5">
                                                <RecencyBiasSlider
                                                    value={recencyBiasValue}
                                                    onChange={handleRecencyBiasChange}
                                                />
                                            </div>
                                            <div className="pt-2 mt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#recency-bias"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 6. Re-ranking */}
                                <Tooltip open={openTooltip === "reRanking"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("reRanking")}
                                            onMouseLeave={() => handleTooltipMouseLeave("reRanking")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.reRanking ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("reRanking", "re-ranking")}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.reRanking
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <ArrowUpWideNarrow className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "max-w-[220px] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("reRanking")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("reRanking")}
                                    >
                                        <div className="space-y-2">
                                            <div className="text-sm font-semibold">AI reranking</div>
                                            <p className="text-xs text-white/90">LLM reorders results for better relevance. Adds latency.</p>
                                            <div className="pt-2 mt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#ai-reranking"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 7. Answer */}
                                <Tooltip open={openTooltip === "answer"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("answer")}
                                            onMouseLeave={() => handleTooltipMouseLeave("answer")}
                                            className={cn(
                                                "h-8 w-8 rounded-md p-0 overflow-hidden border",
                                                toggles.answer ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("answer", "answer")}
                                                className={cn(
                                                    "h-full w-full rounded flex items-center justify-center transition-colors",
                                                    toggles.answer
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <BrainCircuit className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(
                                            "max-w-[220px] p-2.5 rounded-md bg-gray-900 text-white",
                                            "border border-white/10 shadow-lg text-xs"
                                        )}
                                        arrowClassName="fill-gray-900"
                                        onMouseEnter={() => handleTooltipContentMouseEnter("answer")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("answer")}
                                    >
                                        <div className="space-y-2">
                                            <div className="text-sm font-semibold">Generate answer</div>
                                            <p className="text-xs text-white/90">Returns an AI-written answer instead of raw results when enabled.</p>
                                            <div className="pt-2 mt-2 border-t border-white/10">
                                                <a
                                                    href="https://docs.airweave.ai/search#generate-ai-answers"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-white/10 hover:bg-white/20 px-2 py-1 rounded ring-1 ring-white/15"
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </div>

                            {/* Right side send button */}
                            <button
                                type="button"
                                onClick={handleSendQuery}
                                disabled={!hasQuery || isSearching}
                                className={cn(
                                    "h-8 w-8 rounded-md flex items-center justify-center shadow-sm transition-colors",
                                    hasQuery && !isSearching ? "text-white bg-black hover:bg-gray-600 ring-1 ring-white" : "text-gray-400 bg-gray-200 cursor-not-allowed"
                                )}
                                title={hasQuery ? (isSearching ? "Searching..." : "Send query") : "Type a question to enable"}
                            >
                                {isSearching ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <ArrowUp className="h-4 w-4" />
                                )}
                            </button>
                        </TooltipProvider>
                    </div>
                </div>
            </div>

            {/* Code Block Modal Overlay */}
            {showCodeBlock && collectionId && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
                        onClick={() => setShowCodeBlock(false)}
                    />

                    {/* Modal Content */}
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-8 pointer-events-none">
                        <div
                            className={cn(
                                "relative w-full max-w-4xl pointer-events-auto"
                            )}
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Close button */}
                            <button
                                onClick={() => setShowCodeBlock(false)}
                                className={cn(
                                    "absolute top-2 right-2 z-10 h-8 w-8 rounded-md flex items-center justify-center",
                                    "transition-colors",
                                    isDark
                                        ? "bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200"
                                        : "bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-900"
                                )}
                                title="Close (Esc)"
                            >
                                <X className="h-4 w-4" />
                            </button>

                            {/* Just the ApiIntegrationDoc Component */}
                            <ApiIntegrationDoc
                                collectionReadableId={collectionId}
                                query={query || "Ask a question about your data"}
                                searchConfig={{
                                    search_method: searchMethod,
                                    expansion_strategy: toggles.queryExpansion ? "auto" : "no_expansion",
                                    enable_query_interpretation: toggles.queryInterpretation,
                                    recency_bias: toggles.recencyBias ? recencyBiasValue : 0.0,
                                    enable_reranking: toggles.reRanking,
                                    response_type: toggles.answer ? "completion" : "raw"
                                }}
                                filter={toggles.filter ? filterJson : null}
                                apiKey={apiKey}
                            />
                        </div>
                    </div>
                </>
            )}
        </>
    );
};
