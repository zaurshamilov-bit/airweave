import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Terminal, Copy, Check } from "lucide-react";
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
  const [apiDialogTab, setApiDialogTab] = useState<"rest" | "python" | "node">("rest");
  const [copiedPython, setCopiedPython] = useState(false);
  const [copiedNode, setCopiedNode] = useState(false);
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

    return {
      curlSnippet,
      pythonSnippet,
      nodeSnippet
    };
  };

  // Function to handle copying code
  const handleCopyCode = (code: string, type: 'python' | 'node') => {
    navigator.clipboard.writeText(code);

    if (type === 'python') {
      setCopiedPython(true);
      setTimeout(() => setCopiedPython(false), 1500);
    } else {
      setCopiedNode(true);
      setTimeout(() => setCopiedNode(false), 1500);
    }

    toast({
      title: "Copied to clipboard",
      description: `${type === 'python' ? 'Python' : 'JavaScript'} code copied to clipboard`,
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
              <svg className="h-4 w-4" viewBox="0 0 256 255" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin meet">
                <defs>
                  <linearGradient x1="12.959%" y1="12.039%" x2="79.639%" y2="78.201%" id="a">
                    <stop stopColor="#387EB8" offset="0%" />
                    <stop stopColor="#366994" offset="100%" />
                  </linearGradient>
                  <linearGradient x1="19.128%" y1="20.579%" x2="90.742%" y2="88.429%" id="b">
                    <stop stopColor="#FFE052" offset="0%" />
                    <stop stopColor="#FFC331" offset="100%" />
                  </linearGradient>
                </defs>
                <path d="M126.916.072c-64.832 0-60.784 28.115-60.784 28.115l.072 29.128h61.868v8.745H41.631S.145 61.355.145 126.77c0 65.417 36.21 63.097 36.21 63.097h21.61v-30.356s-1.165-36.21 35.632-36.21h61.362s34.475.557 34.475-33.319V33.97S194.67.072 126.916.072zM92.802 19.66a11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13 11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.13z" fill="url(#a)" />
                <path d="M128.757 254.126c64.832 0 60.784-28.115 60.784-28.115l-.072-29.127H127.6v-8.745h86.441s41.486 4.705 41.486-60.712c0-65.416-36.21-63.096-36.21-63.096h-21.61v30.355s1.165 36.21-35.632 36.21h-61.362s-34.475-.557-34.475 33.32v56.013s-5.235 33.897 62.518 33.897zm34.114-19.586a11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.131 11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13z" fill="url(#b)" />
              </svg>
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
              <svg className="h-4 w-4" viewBox="0 0 256 292" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid">
                <defs>
                  <linearGradient x1="68.188%" y1="17.487%" x2="27.823%" y2="89.755%" id="nodejs-gradient-1">
                    <stop stopColor="#41873F" offset="0%"/>
                    <stop stopColor="#418B3D" offset="32.88%"/>
                    <stop stopColor="#419637" offset="63.52%"/>
                    <stop stopColor="#3FA92D" offset="93.19%"/>
                    <stop stopColor="#3FAE2A" offset="100%"/>
                  </linearGradient>
                  <linearGradient x1="43.277%" y1="55.169%" x2="159.245%" y2="-18.306%" id="nodejs-gradient-2">
                    <stop stopColor="#41873F" offset="13.76%"/>
                    <stop stopColor="#54A044" offset="40.32%"/>
                    <stop stopColor="#66B848" offset="71.36%"/>
                    <stop stopColor="#6CC04A" offset="90.81%"/>
                  </linearGradient>
                  <linearGradient x1="-4.389%" y1="49.997%" x2="101.499%" y2="49.997%" id="nodejs-gradient-3">
                    <stop stopColor="#6CC04A" offset="9.192%"/>
                    <stop stopColor="#66B848" offset="28.64%"/>
                    <stop stopColor="#54A044" offset="59.68%"/>
                    <stop stopColor="#41873F" offset="86.24%"/>
                  </linearGradient>
                </defs>
                <g>
                  <path d="M134.923 1.832c-4.344-2.443-9.502-2.443-13.846 0L6.787 67.801C2.443 70.244 0 74.859 0 79.745v132.208c0 4.887 2.715 9.502 6.787 11.945l114.29 65.968c4.344 2.444 9.502 2.444 13.846 0l114.29-65.968c4.344-2.443 6.787-7.058 6.787-11.945V79.745c0-4.886-2.715-9.501-6.787-11.944l-114.29-65.969z" fill="url(#nodejs-gradient-1)"/>
                  <path d="M249.485 67.8L134.651 1.833c-1.086-.543-2.443-1.086-3.53-1.357L2.443 220.912c1.086 1.357 2.444 2.443 3.801 3.258l114.833 65.968c3.258 1.9 7.059 2.443 10.588 1.357l120.806-220.98c-.814-1.085-1.9-1.9-2.986-2.714z" fill="url(#nodejs-gradient-2)"/>
                  <path d="M249.756 223.898c3.258-1.9 5.701-5.158 6.787-8.687L130.58.204c-3.258-.543-6.787-.272-9.773 1.628L6.787 67.53l122.978 224.238c1.628-.272 3.53-.814 5.158-1.629l114.833-66.24z" fill="url(#nodejs-gradient-3)"/>
                </g>
              </svg>
              <span>Node.js</span>
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
