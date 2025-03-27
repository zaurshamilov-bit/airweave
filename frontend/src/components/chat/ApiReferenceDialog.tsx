import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Terminal, Copy, Check, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useToast } from "@/hooks/use-toast";
import { ModelSettings } from "./types";
import { PythonIcon } from "@/components/icons/PythonIcon";
import { NodeIcon } from "@/components/icons/NodeIcon";
import { McpIcon } from "@/components/icons/McpIcon";

interface ApiReferenceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  modelName: string;
  modelSettings: ModelSettings;
  systemPrompt: string;
}

// Create a custom style that removes backgrounds but keeps text coloring
const customStyle = {
  ...materialOceanic,
  'pre[class*="language-"]': {
    ...materialOceanic['pre[class*="language-"]'],
    background: 'transparent',
    margin: 0,
    padding: 0,
  },
  'code[class*="language-"]': {
    ...materialOceanic['code[class*="language-"]'],
    background: 'transparent',
  }
};

export function ApiReferenceDialog({
  open,
  onOpenChange,
  modelName,
  modelSettings,
  systemPrompt,
}: ApiReferenceDialogProps) {
  const [apiDialogTab, setApiDialogTab] = useState<"rest" | "python" | "node" | "mcp">("rest");
  const [copiedPython, setCopiedPython] = useState(false);
  const [copiedNode, setCopiedNode] = useState(false);
  const [copiedMcp, setCopiedMcp] = useState(false);
  const { toast } = useToast();

  // Function to build API URLs from settings
  const getApiEndpoints = () => {
    const baseUrl = window.location.origin;
    const apiUrl = `${baseUrl}/api/v1/search`;

    // Create the JSON body that will be used in all API examples
    const jsonBody = {
      model_name: modelName,
      model_settings: {
        temperature: modelSettings.temperature || 0.7,
        max_tokens: modelSettings.max_tokens || 1000,
        top_p: modelSettings.top_p || 1.0,
        frequency_penalty: modelSettings.frequency_penalty || 0,
        presence_penalty: modelSettings.presence_penalty || 0,
        search_type: modelSettings.search_type || 'vector'
      },
      system_prompt: systemPrompt,
      query: "Your search query here"
    };

    // Create the cURL command
    const curlSnippet = `curl -X POST ${apiUrl} \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(jsonBody, null, 2)}'`;

    // Create the Python code
    const pythonSnippet =
`import requests
import json

url = "${apiUrl}"
headers = {"Content-Type": "application/json"}
payload = ${JSON.stringify(jsonBody, null, 2)}

response = requests.post(url, headers=headers, json=payload)
print(response.json())`;

    // Create the Node.js code
    const nodeSnippet =
`const fetch = require('node-fetch');

const url = "${apiUrl}";
const headers = {"Content-Type": "application/json"};
const payload = ${JSON.stringify(jsonBody, null, 2)};

fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
})
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));`;

    // Create the MCP code (Model Context Protocol)
    const mcpSnippet =
`import { MCPClient } from "@mcp/client";

// Initialize the MCP client with your Airweave endpoint
const client = new MCPClient({
  endpoint: "${apiUrl}",
  version: "0.1.0-beta"
});

// Create a context with your data sources
const context = client.createContext({
  model: "${modelName}",
  systemPrompt: \`${systemPrompt}\`
});

// Execute a search query with MCP
async function searchWithMCP() {
  const result = await context.search({
    query: "Your search query here",
    // Optional MCP-specific parameters
    retrieval: {
      strategy: "hybrid",
      depth: 3,
      sources: ["primary", "knowledge_graph"]
    }
  });

  console.log(result.data);
  console.log(result.metadata.context_used);
}

searchWithMCP();`;

    return {
      curlSnippet,
      pythonSnippet,
      nodeSnippet,
      mcpSnippet
    };
  };

  // Function to handle copying code
  const handleCopyCode = (code: string, type: 'python' | 'node' | 'mcp') => {
    navigator.clipboard.writeText(code);

    if (type === 'python') {
      setCopiedPython(true);
      setTimeout(() => setCopiedPython(false), 1500);
    } else if (type === 'node') {
      setCopiedNode(true);
      setTimeout(() => setCopiedNode(false), 1500);
    } else if (type === 'mcp') {
      setCopiedMcp(true);
      setTimeout(() => setCopiedMcp(false), 1500);
    }

    toast({
      title: "Copied to clipboard",
      description: `${type === 'python' ? 'Python' : type === 'node' ? 'JavaScript' : 'MCP'} code copied to clipboard`,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Search API Reference</DialogTitle>
          <DialogDescription>
            Use these endpoints to access this search functionality programmatically.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4 max-h-[70vh] overflow-y-auto">
          {/* Tabs - styled like SyncTableView.tsx */}
          <div className="flex space-x-1 p-1 rounded-md mb-4 w-fit ">
            <Button
              variant={apiDialogTab === "rest" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("rest")}
              className={cn(
                "rounded-sm text-xs flex items-center gap-2",
                apiDialogTab === "rest"
                  ? "shadow-sm bg-muted"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Terminal className="h-4 w-4" />
              <span>cURL</span>
            </Button>
            <Button
              variant={apiDialogTab === "python" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("python")}
              className={cn(
                "rounded-sm text-xs flex items-center gap-2",
                apiDialogTab === "python"
                  ? "shadow-sm bg-muted"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <PythonIcon className="h-4 w-4" />
              <span>Python</span>
            </Button>
            <Button
              variant={apiDialogTab === "node" ? "default" : "ghost"}
              size="sm"
              onClick={() => setApiDialogTab("node")}
              className={cn(
                "rounded-sm text-xs flex items-center gap-2",
                apiDialogTab === "node"
                  ? "shadow-sm bg-muted"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <NodeIcon className="h-4 w-4" />
              <span>Node.js</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={true}
              className={cn(
                "rounded-sm text-xs flex items-center gap-2 opacity-60 cursor-not-allowed",
                "text-muted-foreground"
              )}
            >
              <McpIcon className="h-4 w-4" />
              <span>MCP</span>
              <Badge className="bg-blue-500 text-xs h-5 ml-1">Coming Soon</Badge>
            </Button>
          </div>

          {/* Tab Content */}
          {apiDialogTab === "rest" && (
            <div className="space-y-4">
              <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
                <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
                  <div className="flex items-center gap-3">
                    <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-xs font-bold px-2 rounded">POST</Badge>
                    <span className="text-sm font-mono">/api/v1/search</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
                      <span className="font-medium">Shell</span>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      onClick={() => {
                        navigator.clipboard.writeText(getApiEndpoints().curlSnippet);
                        toast({
                          title: "Copied to clipboard",
                          description: "cURL command copied to clipboard",
                        });
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="p-4 bg-card">
                  <SyntaxHighlighter
                    language="bash"
                    style={customStyle}
                    customStyle={{
                      fontSize: '0.75rem',
                      background: 'transparent',
                      margin: 0,
                      padding: 0,
                    }}
                    wrapLongLines={false}
                    showLineNumbers={true}
                    codeTagProps={{
                      style: {
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                      }
                    }}
                  >
                    {getApiEndpoints().curlSnippet}
                  </SyntaxHighlighter>
                </div>
              </div>
            </div>
          )}

          {apiDialogTab === "python" && (
            <div className="space-y-2">
              <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
                <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
                  <div className="flex items-center gap-3">
                    <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-xs font-bold px-2 rounded">POST</Badge>
                    <span className="text-sm font-mono">/api/v1/search</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
                      <span className="font-medium">Python</span>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      onClick={() => handleCopyCode(getApiEndpoints().pythonSnippet, 'python')}
                    >
                      {copiedPython ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="p-4 bg-card">
                  <SyntaxHighlighter
                    language="python"
                    style={customStyle}
                    customStyle={{
                      fontSize: '0.75rem',
                      background: 'transparent',
                      margin: 0,
                      padding: 0,
                    }}
                    wrapLongLines={false}
                    showLineNumbers={true}
                    codeTagProps={{
                      style: {
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                      }
                    }}
                  >
                    {getApiEndpoints().pythonSnippet}
                  </SyntaxHighlighter>
                </div>
              </div>
            </div>
          )}

          {apiDialogTab === "node" && (
            <div className="space-y-2">
              <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
                <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
                  <div className="flex items-center gap-3">
                    <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-xs font-bold px-2 rounded">POST</Badge>
                    <span className="text-sm font-mono">/api/v1/search</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
                      <span className="font-medium">JavaScript</span>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      onClick={() => handleCopyCode(getApiEndpoints().nodeSnippet, 'node')}
                    >
                      {copiedNode ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="p-4 bg-card">
                  <SyntaxHighlighter
                    language="javascript"
                    style={customStyle}
                    customStyle={{
                      fontSize: '0.75rem',
                      background: 'transparent',
                      margin: 0,
                      padding: 0,
                    }}
                    wrapLongLines={false}
                    showLineNumbers={true}
                    codeTagProps={{
                      style: {
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                      }
                    }}
                  >
                    {getApiEndpoints().nodeSnippet}
                  </SyntaxHighlighter>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
