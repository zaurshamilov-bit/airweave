import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import { Copy, Check } from 'lucide-react';

export const QueryTool = ({ syncId }) => {
    const [query, setQuery] = useState('');
    const [response, setResponse] = useState('');
    const [objects, setObjects] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [statusCode, setStatusCode] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Don't proceed if query is empty
        if (!query.trim()) return;

        setIsLoading(true);
        setStatusCode(null);

        try {
            // Build URL with query parameters
            const searchParams = new URLSearchParams({
                sync_id: syncId,
                query: query,
                response_type: 'completion'
            });

            const response = await apiClient.get(`/search?${searchParams}`);
            setStatusCode(response.status);

            if (!response.ok) {
                throw new Error(`Search failed: ${response.statusText}`);
            }

            const data = await response.json();

            // Update state with the response
            setResponse(data.completion || '');
            setObjects(JSON.stringify(data.results, null, 2));
        } catch (error) {
            console.error('Error searching:', error);
            setResponse(`Error: ${error.message}`);
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

    return (
        <Card className="mb-4 border-none">
            <CardHeader className="pt-5 pb-1 pl-4">
                <CardTitle className="text-[18px]">Query your collection</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
                <form onSubmit={handleSubmit} className="flex flex-nowrap relative">
                    <div className="min-w-[120px] max-w-[30%] bg-black text-white text-[11px] rounded-md rounded-r-none flex items-center justify-start font-medium overflow-hidden whitespace-nowrap text-ellipsis px-2">
                        respectable-sparrow.airweave.ai/search?query=
                    </div>
                    <Input
                        placeholder="Ask a question about your data..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="flex-1 rounded-l-none"
                    />
                    <Button
                        className='ml-2 shrink-0'
                        type="submit"
                        disabled={isLoading}
                    >
                        {isLoading ? 'Running...' : 'Run'}
                    </Button>
                </form>

                <div className="flex gap-4 mt-4 bg-white rounded-md p-0 pt-0">
                    <div className="flex-1 flex flex-col">
                        <div className="mb-1 px-1">
                            <h3 className="text-[15px] font-semibold">Response</h3>
                        </div>
                        <Card className="h-[200px] overflow-auto p-0 border border-black">
                            <CardContent className="p-3 h-full overflow-x-auto">
                                <pre className="whitespace-pre-wrap break-words m-0 text-[10px]">{response}</pre>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="flex-1 flex flex-col">
                        <div className="mb-1 px-1">
                            <h3 className="text-[15px] font-semibold">Objects found</h3>
                        </div>
                        <Card className="h-[200px] overflow-auto p-0 border border-black bg-black">
                            <CardContent className="p-0 h-full text-white overflow-x-auto relative">
                                <div className="sticky top-0 right-0 flex items-center justify-end gap-4 bg-black z-10 w-full py-1 px-3">                                    {statusCode && (
                                    <span className={`text-xs ${statusCode === 200 ? 'text-green-400' : 'text-red-400'}`}>
                                        response {statusCode}
                                    </span>
                                )}
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-5 w-5 p-0 text-white hover:text-white"
                                        onClick={handleCopyObjects}
                                        disabled={!objects}
                                    >
                                        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                                    </Button>
                                </div>
                                <div className="p-3 pt-1">
                                    <pre className="whitespace-pre-wrap break-all m-0 text-[10px] max-w-full">{objects}</pre>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
