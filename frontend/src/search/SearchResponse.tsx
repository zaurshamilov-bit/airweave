import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Button } from '@/components/ui/button';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import {
    Layers,
    TerminalSquare,
    Clock,
    SearchCode,
    Braces,
    Copy,
    Check,
    FileJson2,
    ExternalLink
} from 'lucide-react';
import { FiMessageSquare } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { JsonViewer } from '@textea/json-viewer';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { CollapsibleCard } from '@/components/ui/CollapsibleCard';

interface SearchResponseProps {
    searchResponse: any;
    isSearching: boolean;
    responseType?: 'raw' | 'completion';
    className?: string;
}

export const SearchResponse: React.FC<SearchResponseProps> = ({
    searchResponse,
    isSearching,
    responseType = 'raw',
    className
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const [copiedCompletion, setCopiedCompletion] = useState(false);
    const [copiedJson, setCopiedJson] = useState(false);

    // Collapsible state with localStorage persistence
    const [isExpanded, setIsExpanded] = useState(() => {
        const stored = localStorage.getItem('searchResponse-expanded');
        return stored ? JSON.parse(stored) : true; // Default to expanded
    });

    // Persist state changes
    useEffect(() => {
        localStorage.setItem('searchResponse-expanded', JSON.stringify(isExpanded));
    }, [isExpanded]);

    // State for active tab - entities first if raw, answer first if completion
    const [activeTab, setActiveTab] = useState<'answer' | 'entities'>(
        responseType === 'completion' ? 'answer' : 'entities'
    );

    // State for tooltip management
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // Ref for JSON viewer container for scrolling to entities
    const jsonViewerRef = useRef<HTMLDivElement>(null);

    // Extract data from response
    const searchStatus = searchResponse?.status || null;
    const statusCode = searchResponse?.error ? searchResponse.status : 200;
    const responseTime = searchResponse?.responseTime || null;
    const completion = searchResponse?.completion || '';
    const results = searchResponse?.results || [];
    const hasError = searchResponse?.error;

    // Debug logging
    useEffect(() => {
        console.log('[SearchResponseDisplay] State changed:', {
            isSearching,
            responseType,
            hasSearchResponse: !!searchResponse,
            searchResponseStatus: searchResponse?.status,
            completionLength: completion?.length,
            completionPreview: completion?.substring(0, 50) + (completion?.length > 50 ? '...' : ''),
            resultsCount: results?.length,
            searchStatus,
            hasError,
            activeTab,
            willReturnNull: !searchResponse && !isSearching
        });

        if (!searchResponse && !isSearching) {
            console.warn('[SearchResponseDisplay] Component will return NULL on next render!');
        }
    }, [isSearching, responseType, searchResponse, completion, results, searchStatus, hasError, activeTab]);

    useEffect(() => {
        if (searchStatus === 'cancelled') {
            console.log('[SearchResponseDisplay] Showing cancelled state with empty content');
        }
    }, [searchStatus]);

    // Memoize expensive style objects
    const syntaxStyle = useMemo(() => isDark ? materialOceanic : oneLight, [isDark]);

    // Create a mapping of entity IDs to source names and numbers
    const entitySourceMap = useMemo(() => {
        const map = new Map<string, { source: string; number: number }>();
        const sourceCounters = new Map<string, number>();

        // Helper function to format source names
        const formatSourceName = (name: string) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ');
        };

        results.forEach((result: any) => {
            const payload = result.payload || result;
            const entityId = payload.entity_id || payload.id || payload._id;
            const rawSourceName = payload.airweave_system_metadata?.source_name || payload.source_name || 'Unknown';
            const sourceName = formatSourceName(rawSourceName);

            if (entityId) {
                // Get or create counter for this source
                let counter = sourceCounters.get(sourceName) || 0;
                counter++;
                sourceCounters.set(sourceName, counter);

                // Store the mapping
                map.set(entityId, {
                    source: sourceName,
                    number: counter
                });
            }
        });

        return map;
    }, [results]);

    // Helper functions for tooltip management with delay
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

    // Get status indicator colors
    const getStatusIndicator = useCallback((status: string | null) => {
        if (!status) return "bg-gray-400";

        switch (status) {
            case 'in_progress':
                return isDark ? "bg-blue-400" : "bg-blue-600";
            case 'success':
                return isDark ? "bg-green-400" : "bg-green-500";
            case 'no_relevant_results':
                return isDark ? "bg-amber-400" : "bg-amber-500";
            case 'cancelled':
                return isDark ? "bg-red-400" : "bg-red-500";
            default:
                return isDark ? "bg-red-400" : "bg-red-500";
        }
    }, [isDark]);

    const handleCopyCompletion = useCallback(async () => {
        await navigator.clipboard.writeText(completion);
    }, [completion]);

    const handleCopyJson = useCallback(async () => {
        await navigator.clipboard.writeText(JSON.stringify(results, null, 2));
    }, [results]);

    // Combined copy function that copies the appropriate content based on active tab
    const handleCopy = useCallback(async () => {
        if (responseType === 'completion' && activeTab === 'answer' && completion) {
            await handleCopyCompletion();
        } else if (activeTab === 'entities' && results.length > 0) {
            await handleCopyJson();
        }
    }, [responseType, activeTab, completion, results, handleCopyCompletion, handleCopyJson]);

    // Handle clicking on entity references in completion
    const handleEntityClick = useCallback((entityId: string) => {
        // Switch to entities tab
        setActiveTab('entities');

        // Wait for tab switch to complete, then scroll to entity
        setTimeout(() => {
            if (!jsonViewerRef.current) return;

            // Find the entity in the results array
            const entityIndex = results.findIndex((result: any) => {
                const payload = result.payload || result;
                return payload.entity_id === entityId ||
                    payload.id === entityId ||
                    payload._id === entityId;
            });

            if (entityIndex === -1) {
                console.warn(`Entity ${entityId} not found in results`);
                return;
            }

            // Try to find the DOM element for this entity in the JsonViewer
            // JsonViewer creates elements with data attributes we can query
            const container = jsonViewerRef.current;

            // Look for the entity_id field in the JSON viewer
            // We'll search for text nodes containing the entity ID
            const walker = document.createTreeWalker(
                container,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        if (node.textContent?.includes(entityId)) {
                            return NodeFilter.FILTER_ACCEPT;
                        }
                        return NodeFilter.FILTER_SKIP;
                    }
                }
            );

            const textNode = walker.nextNode();
            if (textNode && textNode.parentElement) {
                // Scroll the element into view at the top with some context
                textNode.parentElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Highlight the element briefly
                const originalBg = textNode.parentElement.style.backgroundColor;
                textNode.parentElement.style.backgroundColor = isDark ? 'rgba(59, 130, 246, 0.3)' : 'rgba(59, 130, 246, 0.2)';
                textNode.parentElement.style.transition = 'background-color 0.3s';

                setTimeout(() => {
                    if (textNode.parentElement) {
                        textNode.parentElement.style.backgroundColor = originalBg;
                    }
                }, 2000);
            }
        }, 100);
    }, [results, isDark]);

    // Don't show anything if no response and not loading
    // This should only happen before the first search
    if (!searchResponse && !isSearching) {
        console.log('[SearchResponseDisplay] RETURNING NULL - no response and not searching', {
            searchResponse,
            isSearching
        });
        return null;
    }

    // Create header content with status information
    const headerContent = (
        <>
            <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>Response</span>
            <div className="flex items-center gap-3">
                {searchStatus && !hasError && (
                    <div className="flex items-center">
                        <div className={cn(
                            "h-1.5 w-1.5 rounded-full mr-1",
                            getStatusIndicator(searchStatus)
                        )}></div>
                        <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>
                            {searchStatus.replace(/_/g, ' ')}
                        </span>
                    </div>
                )}

                {hasError && (
                    <div className="flex items-center text-red-500">
                        <span className={DESIGN_SYSTEM.typography.sizes.body}>Error</span>
                    </div>
                )}
            </div>

            <div className="flex items-center gap-2.5">
                {statusCode && (
                    <div className={cn("flex items-center opacity-80", DESIGN_SYSTEM.typography.sizes.label)}>
                        <TerminalSquare className={cn(DESIGN_SYSTEM.icons.inline, "mr-1")} strokeWidth={1.5} />
                        <span className="font-mono">HTTP {statusCode}</span>
                    </div>
                )}

                {responseTime && (
                    <div className={cn("flex items-center opacity-80", DESIGN_SYSTEM.typography.sizes.label)}>
                        <Clock className={cn(DESIGN_SYSTEM.icons.inline, "mr-1")} strokeWidth={1.5} />
                        <span className="font-mono">{responseTime}ms</span>
                    </div>
                )}
            </div>
        </>
    );

    // Create status ribbon
    const statusRibbon = (
        <div className="h-1.5 w-full relative overflow-hidden">
            {isSearching ? (
                <>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r from-blue-500 to-indigo-500"
                    )}></div>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r from-transparent via-white/30 to-transparent",
                        "animate-pulse"
                    )}></div>
                </>
            ) : (
                <div className={cn(
                    "absolute inset-0 h-1.5 bg-gradient-to-r",
                    hasError
                        ? "from-red-500 to-red-600"
                        : searchStatus === 'in_progress'
                            ? "from-blue-500 to-indigo-500"
                            : searchStatus === 'success'
                                ? "from-green-500 to-emerald-500"
                                : searchStatus === 'no_relevant_results'
                                    ? "from-amber-400 to-amber-500"
                                    : searchStatus === 'cancelled'
                                        ? "from-red-500 to-red-600"
                                        : "from-gray-400 to-gray-500"
                )}></div>
            )}
        </div>
    );

    return (
        <CollapsibleCard
            header={headerContent}
            statusRibbon={statusRibbon}
            isExpanded={isExpanded}
            onToggle={setIsExpanded}
            onCopy={handleCopy}
            copyTooltip={activeTab === 'answer' ? "Copy answer" : "Copy entities"}
            autoExpandOnSearch={isSearching}
            className={className}
        >
            {/* Content Section with Tabs */}
            <div className="flex flex-col">
                {/* Error Display */}
                {hasError && (
                    <div className={cn(
                        "border-t p-4",
                        isDark ? "border-gray-800/50 bg-red-950/20" : "border-gray-200/50 bg-red-50"
                    )}>
                        <div className={cn(
                            "text-sm",
                            isDark ? "text-red-300" : "text-red-700"
                        )}>
                            {searchResponse.error}
                        </div>
                    </div>
                )}

                {/* Tab Navigation */}
                {!hasError && (
                    <TooltipProvider>
                        <div className={cn(
                            "flex items-center border-t",
                            isDark ? "border-gray-800/50 bg-gray-900/70" : "border-gray-200/50 bg-gray-50"
                        )}>
                            {/* Show tabs based on responseType */}
                            {responseType === 'raw' ? (
                                <>
                                    {/* Entities tab (active) */}
                                    <button
                                        onClick={() => setActiveTab('entities')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'entities'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FileJson2 className="h-3 w-3" strokeWidth={1.5} />
                                            Entities
                                        </div>
                                        {activeTab === 'entities' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>

                                    {/* Answer tab (disabled with tooltip) */}
                                    <Tooltip open={openTooltip === "answerTab"}>
                                        <TooltipTrigger asChild>
                                            <button
                                                onMouseEnter={() => handleTooltipMouseEnter("answerTab")}
                                                onMouseLeave={() => handleTooltipMouseLeave("answerTab")}
                                                className={cn(
                                                    "px-3.5 py-2 text-[13px] font-medium transition-colors relative cursor-not-allowed",
                                                    isDark
                                                        ? "text-gray-600 bg-gray-900/30"
                                                        : "text-gray-400 bg-gray-50/50"
                                                )}
                                            >
                                                <div className="flex items-center gap-1.5 opacity-60">
                                                    <FiMessageSquare className="h-3 w-3" />
                                                    Answer
                                                </div>
                                            </button>
                                        </TooltipTrigger>
                                        <TooltipContent
                                            side="top"
                                            sideOffset={2}
                                            className={cn(
                                                "max-w-[240px] p-2.5 rounded-md bg-gray-900 text-white",
                                                "border border-white/10 shadow-xl"
                                            )}
                                            arrowClassName="fill-gray-900"
                                            onMouseEnter={() => handleTooltipContentMouseEnter("answerTab")}
                                            onMouseLeave={() => handleTooltipContentMouseLeave("answerTab")}
                                        >
                                            <div className="flex items-start gap-1.5">
                                                <FiMessageSquare className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-white/80" />
                                                <p className="text-xs text-white/90 leading-relaxed">
                                                    To get an answer to your question, turn on "Generate answer" when searching.
                                                </p>
                                            </div>
                                        </TooltipContent>
                                    </Tooltip>
                                </>
                            ) : (
                                <>
                                    {/* Answer tab (active) */}
                                    <button
                                        onClick={() => setActiveTab('answer')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'answer'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FiMessageSquare className="h-3 w-3" />
                                            Answer
                                        </div>
                                        {activeTab === 'answer' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>

                                    {/* Entities tab */}
                                    <button
                                        onClick={() => setActiveTab('entities')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'entities'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FileJson2 className="h-3 w-3" strokeWidth={1.5} />
                                            Entities
                                        </div>
                                        {activeTab === 'entities' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>
                                </>
                            )}
                        </div>
                    </TooltipProvider>
                )}

                {/* Tab Content */}
                {!hasError && (
                    <div className={cn(
                        "border-t relative",
                        isDark ? "border-gray-800/50" : "border-gray-200/50"
                    )}>
                        {/* Answer Tab Content - Always rendered but hidden when not active */}
                        {responseType === 'completion' && (completion || isSearching) && (
                            <div style={{ display: activeTab === 'answer' ? 'block' : 'none' }}>


                                <div className={cn(
                                    "overflow-auto max-h-[438px] leading-relaxed",
                                    DESIGN_SYSTEM.spacing.padding.compact,
                                    DESIGN_SYSTEM.typography.sizes.label,
                                    isDark ? "bg-gray-900 text-gray-200" : "bg-white text-gray-800"
                                )}>
                                    {(() => {
                                        const showingSkeleton = isSearching && !completion;
                                        const showingCompletion = !!completion;
                                        const showingCursor = isSearching && completion;

                                        console.log('[SearchResponseDisplay] Completion rendering logic:', {
                                            isSearching,
                                            hasCompletion: !!completion,
                                            completionLength: completion?.length,
                                            showingSkeleton,
                                            showingCompletion,
                                            showingCursor,
                                            completionSource: isSearching ? 'STREAMING' : 'FINAL'
                                        });

                                        return null; // This return is just for the IIFE
                                    })()}
                                    {isSearching && !completion ? (
                                        // Show skeleton only if we're searching but have no completion yet
                                        <div className="animate-pulse h-32 w-full">
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                                        </div>
                                    ) : completion ? (
                                        // Show the actual completion (streaming or final)
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                h1: ({ node, ...props }) => <h1 className="text-[13px] font-semibold mt-0 mb-1.5" {...props} />,
                                                h2: ({ node, ...props }) => <h2 className="text-[12px] font-semibold mt-0 mb-1.5" {...props} />,
                                                h3: ({ node, ...props }) => <h3 className="text-[12px] font-medium mt-0 mb-1.5" {...props} />,
                                                ul: ({ node, ...props }) => <ul className="list-disc pl-4 mt-0 mb-1 space-y-0.5" {...props} />,
                                                ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mt-0 mb-1 space-y-0.5" {...props} />,
                                                table: ({ node, ...props }) => (
                                                    <div className="overflow-x-auto my-4">
                                                        <table className={cn(
                                                            "min-w-full divide-y",
                                                            isDark ? "divide-gray-700" : "divide-gray-200"
                                                        )} {...props} />
                                                    </div>
                                                ),
                                                thead: ({ node, ...props }) => (
                                                    <thead className={cn(
                                                        isDark ? "bg-gray-800/50" : "bg-gray-50"
                                                    )} {...props} />
                                                ),
                                                tbody: ({ node, ...props }) => (
                                                    <tbody className={cn(
                                                        "divide-y",
                                                        isDark ? "divide-gray-800 bg-gray-900/30" : "divide-gray-200 bg-white"
                                                    )} {...props} />
                                                ),
                                                tr: ({ node, ...props }) => (
                                                    <tr className={cn(
                                                        "transition-colors",
                                                        isDark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"
                                                    )} {...props} />
                                                ),
                                                th: ({ node, ...props }) => (
                                                    <th className={cn(
                                                        "px-3 py-1.5 text-left text-[11px] font-medium uppercase tracking-wider",
                                                        isDark ? "text-gray-300" : "text-gray-700"
                                                    )} {...props} />
                                                ),
                                                td: ({ node, ...props }) => (
                                                    <td className={cn(
                                                        "px-3 py-1.5 text-[12px]",
                                                        isDark ? "text-gray-300" : "text-gray-700"
                                                    )} {...props} />
                                                ),
                                                li: ({ children, ...props }) => {
                                                    // Process list item content to replace [[entity_id]] with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by entity reference pattern [[entity_id]]
                                                            const parts = child.split(/(\[\[[^\]]+\]\])/g);
                                                            return parts.map((part, index) => {
                                                                const match = part.match(/^\[\[([^\]]+)\]\]$/);
                                                                if (match) {
                                                                    const entityId = match[1];
                                                                    const sourceInfo = entitySourceMap.get(entityId);
                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : entityId;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(entityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={`View in Entities tab`}
                                                                        >
                                                                            {displayText}
                                                                        </button>
                                                                    );
                                                                }
                                                                return part;
                                                            });
                                                        }
                                                        return child;
                                                    });
                                                    return <li className="my-0.5" {...props}>{processedChildren}</li>;
                                                },
                                                p: ({ children, ...props }) => {
                                                    // Process paragraph content to replace [[entity_id]] with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by entity reference pattern [[entity_id]]
                                                            const parts = child.split(/(\[\[[^\]]+\]\])/g);
                                                            return parts.map((part, index) => {
                                                                const match = part.match(/^\[\[([^\]]+)\]\]$/);
                                                                if (match) {
                                                                    const entityId = match[1];
                                                                    const sourceInfo = entitySourceMap.get(entityId);
                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : entityId;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(entityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={`View in Entities tab`}
                                                                        >
                                                                            {displayText}
                                                                        </button>
                                                                    );
                                                                }
                                                                return part;
                                                            });
                                                        }
                                                        return child;
                                                    });
                                                    return <p className="mt-0 mb-1 leading-relaxed" {...props}>{processedChildren}</p>;
                                                },
                                                blockquote: ({ node, ...props }) => (
                                                    <blockquote className={cn(
                                                        "border-l-4 pl-4 my-3 italic",
                                                        isDark ? "border-gray-600 text-gray-300" : "border-gray-300 text-gray-700"
                                                    )} {...props} />
                                                ),
                                                hr: ({ node, ...props }) => (
                                                    <hr className={cn(
                                                        "my-2",
                                                        isDark ? "border-gray-700" : "border-gray-300"
                                                    )} {...props} />
                                                ),
                                                strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                                                em: ({ node, ...props }) => <em className="italic" {...props} />,
                                                code(props) {
                                                    const { children, className, node, ...rest } = props;
                                                    const match = /language-(\w+)/.exec(className || '');
                                                    return match ? (
                                                        <SyntaxHighlighter
                                                            language={match[1]}
                                                            style={syntaxStyle}
                                                            customStyle={{
                                                                margin: '0.25rem 0',
                                                                borderRadius: '0.5rem',
                                                                fontSize: '0.75rem',
                                                                padding: '0.75rem',
                                                                background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.95)'
                                                            }}
                                                        >
                                                            {String(children).replace(/\n$/, '')}
                                                        </SyntaxHighlighter>
                                                    ) : (
                                                        <code className={cn(
                                                            "px-1 py-0.5 rounded text-[12px] font-mono",
                                                            isDark
                                                                ? "bg-gray-800 text-gray-300"
                                                                : "bg-gray-100 text-gray-800"
                                                        )} {...rest}>
                                                            {children}
                                                        </code>
                                                    );
                                                }
                                            }}
                                        >
                                            {completion}
                                        </ReactMarkdown>
                                    ) : null}
                                </div>
                            </div>
                        )}

                        {/* Entities Tab Content - Always rendered but hidden when not active */}
                        {(results.length > 0 || isSearching) && (
                            <div style={{ display: activeTab === 'entities' ? 'block' : 'none' }}>
                                <div className={cn(
                                    "overflow-auto max-h-[438px]",
                                    isDark ? "bg-gray-900" : "bg-white"
                                )}>
                                    {isSearching ? (
                                        <div className={cn(
                                            DESIGN_SYSTEM.spacing.padding.default,
                                            "animate-pulse space-y-2"
                                        )}>
                                            <div className="flex gap-2">
                                                <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-36 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="h-4 w-8 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                        </div>
                                    ) : (
                                        <div className={cn(
                                            DESIGN_SYSTEM.spacing.padding.compact,
                                            DESIGN_SYSTEM.typography.sizes.label
                                        )} ref={jsonViewerRef}>
                                            <JsonViewer
                                                value={results}
                                                theme={isDark ? "dark" : "light"}
                                                style={{
                                                    fontSize: '0.68rem',
                                                    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
                                                }}
                                                rootName={false}
                                                displayDataTypes={false}
                                                enableClipboard={false}
                                                quotesOnKeys={false}
                                                indentWidth={2}
                                                collapseStringsAfterLength={100}
                                                groupArraysAfterLength={100}
                                                defaultInspectDepth={10}
                                                defaultInspectControl={(path, value) => {
                                                    // Collapse airweave_system_metadata by default
                                                    if (path.includes('airweave_system_metadata')) {
                                                        return false;
                                                    }
                                                    // Expand all other nodes by default for better entity visibility
                                                    return true;
                                                }}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </CollapsibleCard>
    );
};
