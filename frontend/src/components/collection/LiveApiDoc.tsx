import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import { Copy, Check, Terminal, Settings, Code } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { CodeBlock } from '@/components/ui/code-block';
import { PythonIcon } from '@/components/icons/PythonIcon';
import { NodeIcon } from '@/components/icons/NodeIcon';
import { McpIcon } from '@/components/icons/McpIcon';
import { ClaudeIcon } from '@/components/icons/ClaudeIcon';
import { CursorIcon } from '@/components/icons/CursorIcon';
import { WindsurfIcon } from '@/components/icons/WindsurfIcon';

export const LiveApiDoc = ({ syncId }) => {
    // Add new state for tracking view mode (RestAPI or MCP Server)
    const [viewMode, setViewMode] = useState<"restapi" | "mcpserver">("mcpserver");
    // Updated to handle both RestAPI and MCP Server tabs
    const [apiTab, setApiTab] = useState<"rest" | "python" | "node" | "claude" | "cursor" | "windsurf" | "server">("claude");
    const lastUserMessage = "Your search query here";

    // Reset tab when switching view modes to avoid invalid states
    const handleViewModeChange = (mode: "restapi" | "mcpserver") => {
        setViewMode(mode);
        if (mode === "restapi") {
            setApiTab("rest");
        } else {
            setApiTab("claude");
        }
    };

    // Function to build API URLs from settings
    const getApiEndpoints = () => {
        const baseUrl = window.location.origin;
        const apiUrl = `${baseUrl}/search`;

        // Create the cURL command
        const curlSnippet = `curl -G ${apiUrl}/ \\
         -d sync_id="${syncId}" \\
         -d query="${lastUserMessage}"`;

        // Create the Python code
        const pythonSnippet =
            `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)
client.search.search(
    sync_id="${syncId}",
    query="${lastUserMessage}",
)`;

        // Create the Node.js code
        const nodeSnippet =
            `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });
await client.search.search({
    syncId: "${syncId}",
    query: "${lastUserMessage}"
});`;

        // MCP Server code examples
        const configSnippet =
            `# MCP Server Configuration
`;


        const cliSnippet =
            `# MCP Server CLI
mcp-cli connect --server localhost:8000 --auth-token YOUR_API_KEY
mcp-cli query search --sync-id ${syncId} --query "${lastUserMessage}"
`;

        return {
            curlSnippet,
            pythonSnippet,
            nodeSnippet,
            configSnippet,
            cliSnippet
        };
    };

    const docLinkFooter = (
        <div className="text-xs flex items-center gap-2 text-white">
            <span>→</span>
            <a
                href="https://docs.airweave.ai/api-reference/search"
                target="_blank"
                rel="noopener noreferrer"
                className="text-white hover:text-white hover:underline transition-all"
            >
                Explore the full API documentation
            </a>
        </div>
    );

    return (
        <Card className="mb-8 border-none">
            <CardHeader className="pt-5 pb-1 pl-4">
                <CardTitle className="text-[18px]">Integrate with the endpoint</CardTitle>
            </CardHeader>

            <div className="flex w-full">
                {/* Left 1/4 with view mode buttons */}
                <div className="w-1/4 pl-4 pr-2 flex flex-col gap-2">
                    <Button
                        variant="ghost"
                        onClick={() => handleViewModeChange("mcpserver")}
                        className={cn(
                            "w-full max-w-[200px] justify-start rounded-sm text-sm flex items-center gap-2 bg-white hover:bg-white text-black hover:text-black font-semibold border-[2px]",
                            viewMode === "mcpserver"
                                ? "border-black"
                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(0,0,0,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(0,0,0,0.7)]"
                        )}
                    >
                        MCP Server
                    </Button>
                    <Button
                        variant="ghost"
                        onClick={() => handleViewModeChange("restapi")}
                        className={cn(
                            "w-full max-w-[200px] justify-start rounded-sm text-sm flex items-center gap-2 bg-white hover:bg-white text-black hover:text-black font-semibold border-[2px]",
                            viewMode === "restapi"
                                ? "border-black"
                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(0,0,0,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(0,0,0,0.7)]"
                        )}
                    >
                        RestAPI
                    </Button>
                </div>

                {/* Right 3/4 content */}
                <div className="w-3/4">
                    <div className="bg-black rounded-md p-1">
                        {/* Tabs - Different tabs based on view mode */}
                        <div className="flex space-x-1 p-1 rounded-md mb-1 w-fit">
                            {viewMode === "restapi" ? (
                                <>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("rest")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "rest"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <Terminal className="h-5 w-5" />
                                        <span>cURL</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("python")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "python"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <PythonIcon className="h-5 w-5" />
                                        <span>Python</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("node")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "node"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <NodeIcon className="h-5 w-5" />
                                        <span>Node.js</span>
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("claude")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "claude"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <ClaudeIcon className="h-8 w-8" />
                                        <span>Claude</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("cursor")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "cursor"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <CursorIcon className="h-7 w-7" />
                                        <span>Cursor</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("windsurf")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "windsurf"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <WindsurfIcon className="h-6 w-6" />
                                        <span>Windsurf</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("server")}
                                        className={cn(
                                            "rounded-sm text-sm flex items-center gap-2 bg-black hover:bg-black text-white hover:text-white border-[2px]",
                                            apiTab === "server"
                                                ? "border-white"
                                                : "border-transparent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.3)] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.7)]"
                                        )}
                                    >
                                        <McpIcon className="h-5 w-5" />
                                        <span>Server/Other</span>
                                    </Button>
                                </>
                            )}
                        </div>

                        {/* Tab Content - Different content based on both view mode and tab */}
                        <div className="h-[250px]">
                            {viewMode === "restapi" && (
                                <>
                                    {apiTab === "rest" && (
                                        <CodeBlock
                                            code={getApiEndpoints().curlSnippet}
                                            language="bash"
                                            badgeText="GET"
                                            badgeColor="bg-emerald-600 hover:bg-emerald-600"
                                            title="/search"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}

                                    {apiTab === "python" && (
                                        <CodeBlock
                                            code={getApiEndpoints().pythonSnippet}
                                            language="python"
                                            badgeText="SDK"
                                            badgeColor="bg-blue-600 hover:bg-blue-600"
                                            title="AirweaveSDK"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}

                                    {apiTab === "node" && (
                                        <CodeBlock
                                            code={getApiEndpoints().nodeSnippet}
                                            language="javascript"
                                            badgeText="SDK"
                                            badgeColor="bg-blue-600 hover:bg-blue-600"
                                            title="AirweaveSDKClient"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}
                                </>
                            )}

                            {viewMode === "mcpserver" && (
                                <>
                                    {apiTab === "claude" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}

                                    {apiTab === "cursor" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}

                                    {apiTab === "windsurf" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}

                                    {apiTab === "server" && (
                                        <CodeBlock
                                            code={getApiEndpoints().cliSnippet}
                                            language="bash"
                                            badgeText="SERVER"
                                            badgeColor="bg-gray-600 hover:bg-gray-600"
                                            title="MCP Command Line"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full"
                                        />
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </Card>
    );
};
