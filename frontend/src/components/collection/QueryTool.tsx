import React, { useState, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import { Copy, Check, Database, SearchCode, TerminalSquare, Clock, AlertCircle, ChevronDown, ChevronRight, Code, Layers } from 'lucide-react';
import { useTheme } from '@/lib/theme-provider';
import { cn } from '@/lib/utils';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

interface QueryToolProps {
    syncId?: string;
    collectionReadableId?: string;
}

// Define response type enum to match backend
type ResponseType = 'raw' | 'completion';

export const QueryTool = ({ collectionReadableId }: QueryToolProps) => {
    const [query, setQuery] = useState('');
    const [responseType, setResponseType] = useState<ResponseType>('raw');
    const [completion, setCompletion] = useState('');
    const [objects, setObjects] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [statusCode, setStatusCode] = useState<number | null>(null);
    const [responseTime, setResponseTime] = useState<number | null>(null);
    const [searchStatus, setSearchStatus] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'knowledge' | 'json'>('knowledge');
    const [expandedMetadata, setExpandedMetadata] = useState(true);
    const { resolvedTheme } = useTheme();
    const responseRef = useRef<HTMLDivElement>(null);
    const isDark = resolvedTheme === 'dark';

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Don't proceed if query is empty
        if (!query.trim()) return;

        setIsLoading(true);
        setStatusCode(null);
        setResponseTime(null);
        setSearchStatus(null);
        const startTime = performance.now();

        try {
            // Use the collections search endpoint with response_type parameter
            const response = await apiClient.get(
                `/collections/${collectionReadableId}/search?query=${encodeURIComponent(query)}&response_type=${responseType}`
            );
            const endTime = performance.now();
            setResponseTime(Math.round(endTime - startTime));
            setStatusCode(response.status);

            if (!response.ok) {
                throw new Error(`Search failed: ${response.statusText}`);
            }

            const data = await response.json();

            // Update state based on the response format
            setSearchStatus(data.status || null);
            setObjects(JSON.stringify(data.results || [], null, 2));

            if (responseType === 'completion') {
                setCompletion(data.completion || '');
            } else {
                setCompletion('');
            }

            // Scroll to the response section
            if (responseRef.current) {
                responseRef.current.scrollIntoView({ behavior: 'smooth' });
            }
        } catch (error) {
            console.error('Error searching:', error);
            setCompletion(`Error: ${error instanceof Error ? error.message : String(error)}`);
            setObjects('');
        } finally {
            setIsLoading(false);
        }
    };

    const handleCopyObjects = async () => {
        try {
            await navigator.clipboard.writeText(objects);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    };

    const handleCopyCompletion = async () => {
        try {
            await navigator.clipboard.writeText(completion);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    };

    // Format API URL for display
    const getApiUrl = () => {
        const baseUrl = `api.airweave.ai/collections/${collectionReadableId || '{collection_id}'}/search`;
        const params = [];

        if (query) {
            params.push(`query=${query}`);
        }
        params.push(`response_type=${responseType}`);

        return `${baseUrl}?${params.join('&')}`;
    };

    // JSON syntax highlighting styles
    const syntaxStyle = isDark ? materialOceanic : oneLight;

    // Create a custom style that maintains text coloring but fits our design
    const customSyntaxStyle = {
        ...syntaxStyle,
        'pre[class*="language-"]': {
            ...syntaxStyle['pre[class*="language-"]'],
            background: 'transparent',
            margin: 0,
            padding: 0,
        },
        'code[class*="language-"]': {
            ...syntaxStyle['code[class*="language-"]'],
            background: 'transparent',
        }
    };

    // Get status indicator colors
    const getStatusIndicator = (status: string | null) => {
        if (!status) return "bg-gray-400";

        switch (status) {
            case 'success':
                return isDark ? "bg-green-400" : "bg-green-500";
            case 'no_relevant_results':
                return isDark ? "bg-amber-400" : "bg-amber-500";
            default:
                return isDark ? "bg-red-400" : "bg-red-500";
        }
    };

    // Get accent color based on active tab
    const getAccentColor = () => {
        return activeTab === 'knowledge'
            ? (isDark ? "from-indigo-900/50 to-indigo-950/30" : "from-indigo-50 to-indigo-100/50")
            : (isDark ? "from-gray-800/90 to-gray-900/70" : "from-gray-50 to-gray-100/70");
    };

    const getAccentText = () => {
        return activeTab === 'knowledge'
            ? (isDark ? "text-indigo-300" : "text-indigo-700")
            : (isDark ? "text-gray-300" : "text-gray-700");
    };

    return (
        <div className="w-full mb-6">
            {/* Header with collection name */}
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-xl font-medium text-foreground">Query your collection</h2>
                </div>
            </div>

            {/* API Endpoint display */}
            <div className="mb-5">
                <div className="flex h-8 items-stretch rounded-md border overflow-hidden shadow-xs">
                    <div className={cn(
                        "flex items-center justify-center min-w-[48px]",
                        isDark ? "bg-emerald-900/40 text-emerald-300" : "bg-emerald-50 text-emerald-500"
                    )}>
                        <span className="text-xs font-semibold">GET</span>
                    </div>
                    <div className={cn(
                        "flex-grow flex items-center px-3 py-1.5 text-xs font-mono",
                        isDark
                            ? "bg-gray-900 text-gray-300"
                            : "bg-gray-50/80 text-gray-700"
                    )}>
                        <span className="opacity-75">{getApiUrl()}</span>
                    </div>
                    <div className="border-l flex items-center">
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn(
                                "h-8 w-8 rounded-none",
                                isDark ? "text-gray-400 hover:text-gray-300" : "text-gray-500 hover:text-gray-700"
                            )}
                            onClick={() => navigator.clipboard.writeText(`https://${getApiUrl()}`)}
                        >
                            <Copy className="h-3.5 w-3.5" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Query input */}
            <div className="mb-5">
                <form onSubmit={handleSubmit} className="flex items-stretch">
                    {/* Query input field */}
                    <div className="flex flex-1 h-9 rounded-l-md border-y border-l overflow-hidden">
                        <div className={cn(
                            "flex items-center justify-center min-w-[70px] border-r",
                            isDark
                                ? "bg-gray-800/80 text-gray-300 border-gray-700"
                                : "bg-gray-50/80 text-gray-600 border-gray-200"
                        )}>
                            <span className="text-xs font-medium">query=</span>
                        </div>
                        <input
                            type="text"
                            placeholder="Ask a question about your data..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className={cn(
                                "w-full px-3 h-full text-sm",
                                isDark
                                    ? "bg-gray-900 text-gray-200"
                                    : "bg-white/90"
                            )}
                            style={{ outline: 'none', border: 'none' }}
                        />
                    </div>

                    {/* Response type selector */}
                    <div className={cn(
                        "h-9 border-y border-l border-r-0",
                        isDark ? "border-gray-700" : "border-gray-200"
                    )}>
                        <Select
                            value={responseType}
                            onValueChange={(value) => setResponseType(value as ResponseType)}
                        >
                            <SelectTrigger
                                className={cn(
                                    "h-full border-0 rounded-none min-w-[120px] text-xs font-mono focus:outline-none focus:ring-0 focus:ring-offset-0",
                                    isDark ? "bg-gray-800" : "bg-gray-50"
                                )}
                            >
                                <span>{responseType}</span>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="raw" className="text-xs font-mono">raw</SelectItem>
                                <SelectItem value="completion" className="text-xs font-mono">completion</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Search button */}
                    <Button
                        type="submit"
                        disabled={isLoading || !query.trim()}
                        className={cn(
                            "rounded-l-none rounded-r-md h-9 px-5",
                            isDark
                                ? query.trim() ? "bg-blue-600 hover:bg-blue-700" : "bg-blue-600/90 hover:bg-blue-600/60"
                                : query.trim() ? "bg-blue-500 hover:bg-blue-600" : "bg-blue-500/90 hover:bg-blue-500/60"
                        )}
                    >
                        {isLoading ? 'Searching...' : 'Search'}
                    </Button>
                </form>
            </div>

            {/* Unified Response Section */}
            {(completion || objects) && (
                <div ref={responseRef} className={cn(
                    "mt-8 rounded-lg shadow-sm overflow-hidden",
                    isDark ? "bg-gray-950" : "bg-white",
                    isDark ? "ring-1 ring-gray-800" : "ring-1 ring-gray-200"
                )}>
                    {/* Status Ribbon - Always visible */}
                    <div className={cn(
                        "h-1.5 w-full bg-gradient-to-r",
                        searchStatus === 'success'
                            ? "from-green-500 to-emerald-500"
                            : searchStatus === 'no_relevant_results'
                                ? "from-amber-400 to-amber-500"
                                : "from-gray-400 to-gray-500"
                    )}></div>

                    {/* Metadata Section - Collapsible */}
                    <div className={cn(
                        "transition-all duration-200",
                        isDark ? "bg-gray-900/60" : "bg-gray-50/80"
                    )}>
                        <button
                            onClick={() => setExpandedMetadata(!expandedMetadata)}
                            className={cn(
                                "w-full flex items-center justify-between py-2 px-3",
                                isDark ? "hover:bg-gray-800/50" : "hover:bg-gray-100/50"
                            )}
                        >
                            <div className="flex items-center gap-2">
                                <Layers className="h-3.5 w-3.5 opacity-70" />
                                <span className="text-xs font-medium">Response Metadata</span>
                                {searchStatus && (
                                    <div className="flex items-center ml-2">
                                        <div className={cn(
                                            "h-1.5 w-1.5 rounded-full mr-1.5",
                                            getStatusIndicator(searchStatus)
                                        )}></div>
                                        <span className="text-xs opacity-70">
                                            {searchStatus.replace(/_/g, ' ')}
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                {statusCode && (
                                    <div className="flex items-center text-xs opacity-70">
                                        <span className="font-mono">{statusCode}</span>
                                    </div>
                                )}
                                {responseTime && (
                                    <div className="flex items-center text-xs opacity-70">
                                        <Clock className="h-3 w-3 mr-1" />
                                        <span className="font-mono">{responseTime}ms</span>
                                    </div>
                                )}
                                {expandedMetadata ?
                                    <ChevronDown className="h-3.5 w-3.5 opacity-70" /> :
                                    <ChevronRight className="h-3.5 w-3.5 opacity-70" />
                                }
                            </div>
                        </button>

                        {/* Expanded metadata details */}
                        {expandedMetadata && (
                            <div className={cn(
                                "grid grid-cols-3 divide-x border-t text-xs py-2",
                                isDark ? "divide-gray-800 border-gray-800" : "divide-gray-200 border-gray-200"
                            )}>
                                {/* Status */}
                                {searchStatus && (
                                    <div className="flex items-center py-1.5 px-4">
                                        <div className="flex items-center">
                                            <AlertCircle className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                                            <span className="font-medium">
                                                Status: <span className="opacity-70">{searchStatus.replace(/_/g, ' ')}</span>
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* Status code */}
                                <div className="flex items-center py-1.5 px-4">
                                    <div className="flex items-center">
                                        <TerminalSquare className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                                        <span className="font-medium">
                                            Response: <span className="font-mono opacity-70">{statusCode || '---'}</span>
                                        </span>
                                    </div>
                                </div>

                                {/* Response time */}
                                <div className="flex items-center py-1.5 px-4">
                                    <div className="flex items-center">
                                        <Clock className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                                        <span className="font-medium">
                                            Time: <span className="font-mono opacity-70">{responseTime ? `${responseTime}ms` : '---'}</span>
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Tab Navigation - Show when both types of data are available */}
                    {completion && objects && (
                        <div className={cn(
                            "flex border-b px-2 pt-2",
                            isDark ? "border-gray-800" : "border-gray-200"
                        )}>
                            <button
                                onClick={() => setActiveTab('knowledge')}
                                className={cn(
                                    "flex items-center px-3 py-1.5 text-xs font-medium rounded-t-md mr-1",
                                    activeTab === 'knowledge' ? (
                                        isDark
                                            ? "text-indigo-300 bg-indigo-950/30 border-b-2 border-indigo-500"
                                            : "text-indigo-700 bg-indigo-50 border-b-2 border-indigo-500"
                                    ) : (
                                        isDark
                                            ? "text-gray-400 hover:text-gray-300 hover:bg-gray-800/50"
                                            : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                                    )
                                )}
                            >
                                <SearchCode className="h-3.5 w-3.5 mr-1.5" />
                                Knowledge
                            </button>
                            <button
                                onClick={() => setActiveTab('json')}
                                className={cn(
                                    "flex items-center px-3 py-1.5 text-xs font-medium rounded-t-md",
                                    activeTab === 'json' ? (
                                        isDark
                                            ? "text-gray-200 bg-gray-800 border-b-2 border-gray-500"
                                            : "text-gray-700 bg-gray-50 border-b-2 border-gray-500"
                                    ) : (
                                        isDark
                                            ? "text-gray-400 hover:text-gray-300 hover:bg-gray-800/50"
                                            : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                                    )
                                )}
                            >
                                <Code className="h-3.5 w-3.5 mr-1.5" />
                                JSON
                            </button>
                        </div>
                    )}

                    {/* Content Section - Shows based on available data and active tab */}
                    <div>
                        {/* Knowledge Response - shown when completion exists and is active tab or when only completion exists */}
                        {completion && (responseType === 'completion') && ((!objects || activeTab === 'knowledge')) && (
                            <div>
                                <div className={cn(
                                    "flex items-center justify-between p-3 border-b bg-gradient-to-r",
                                    isDark
                                        ? "from-indigo-950/30 to-indigo-900/20 border-indigo-900/40 text-indigo-300"
                                        : "from-indigo-50 to-indigo-100/50 border-indigo-100 text-indigo-700"
                                )}>
                                    <div className="flex items-center">
                                        <SearchCode className="h-3.5 w-3.5 mr-2" />
                                        <span className="text-xs font-semibold">Knowledge Response</span>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className={cn(
                                            "text-xs gap-1 h-6",
                                            isDark ? "text-indigo-300 hover:text-indigo-200" : "text-indigo-600 hover:text-indigo-700"
                                        )}
                                        onClick={handleCopyCompletion}
                                    >
                                        <Copy className="h-3 w-3" />
                                        Copy
                                    </Button>
                                </div>

                                <div className={cn(
                                    "p-4 prose max-w-none overflow-auto max-h-[400px]",
                                    isDark
                                        ? "prose-invert bg-gradient-to-b from-gray-900/70 to-gray-900/50 text-gray-200"
                                        : "bg-gradient-to-b from-white to-gray-50/80 prose-gray text-gray-800"
                                )}
                                style={{ fontSize: '0.875rem' }}>
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            h1: ({node, ...props}) => <h1 style={{fontSize: '2em', fontWeight: 'bold', margin: '0.67em 0'}} {...props}/>,
                                            h2: ({node, ...props}) => <h2 style={{fontSize: '1.5em', fontWeight: 'bold', margin: '0.83em 0'}} {...props}/>,
                                            h3: ({node, ...props}) => <h3 style={{fontSize: '1.17em', fontWeight: 'bold', margin: '1em 0'}} {...props}/>,
                                            ul: ({node, ...props}) => <ul style={{listStyle: 'disc', paddingLeft: '2em', margin: '1em 0'}} {...props}/>,
                                            li: ({node, ...props}) => <li style={{display: 'list-item', margin: '0.5em 0'}} {...props}/>,
                                            code(props) {
                                                const {children, className, node, ...rest} = props;
                                                const match = /language-(\w+)/.exec(className || '');
                                                return match ? (
                                                    <SyntaxHighlighter
                                                        language={match[1]}
                                                        style={isDark ? materialOceanic : oneLight}
                                                        customStyle={{
                                                            margin: 0,
                                                            borderRadius: '0.75rem',
                                                            background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.8)'
                                                        }}
                                                    >
                                                        {String(children).replace(/\n$/, '')}
                                                    </SyntaxHighlighter>
                                                ) : (
                                                    <code {...rest} className={cn(className, "bg-opacity-75 px-1.5 py-0.5 rounded text-sm")}>
                                                        {children}
                                                    </code>
                                                );
                                            }
                                        }}
                                    >
                                        {completion}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}

                        {/* JSON Response - shown when objects exists and is active tab or when only objects exists */}
                        {objects && (!completion || activeTab === 'json') && (
                            <div>
                                <div className={cn(
                                    "flex items-center justify-between p-3 border-b bg-gradient-to-r",
                                    isDark
                                        ? "from-gray-800/90 to-gray-900/70 border-gray-700 text-gray-300"
                                        : "from-gray-50 to-gray-100/70 border-gray-200 text-gray-700"
                                )}>
                                    <div className="flex items-center">
                                        <Database className="h-3.5 w-3.5 mr-2 opacity-80" />
                                        <span className="text-xs font-semibold">JSON RESPONSE</span>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-xs gap-1 h-6"
                                        onClick={handleCopyObjects}
                                    >
                                        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                                        Copy
                                    </Button>
                                </div>
                                <div className={cn(
                                    "overflow-auto max-h-[400px] bg-gradient-to-b",
                                    isDark ? "from-gray-900/80 to-gray-900/60" : "from-white to-gray-50/80"
                                )}>
                                    <SyntaxHighlighter
                                        language="json"
                                        style={customSyntaxStyle}
                                        customStyle={{
                                            fontSize: '0.8rem',
                                            background: 'transparent',
                                            padding: '1rem',
                                            margin: 0
                                        }}
                                        showLineNumbers={true}
                                    >
                                        {objects}
                                    </SyntaxHighlighter>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
