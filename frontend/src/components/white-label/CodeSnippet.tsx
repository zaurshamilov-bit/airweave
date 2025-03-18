import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check, Terminal } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeSnippetProps {
  whitelabelGuid: string;
  frontendUrl?: string;
  clientId?: string;
  source?: string;
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

export const CodeSnippet = ({ whitelabelGuid, frontendUrl, clientId, source }: CodeSnippetProps) => {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<"auth" | "implementation">("auth");
  const [copiedAuth, setCopiedAuth] = useState(false);
  const [copiedImplementation, setCopiedImplementation] = useState(false);

  const hasWhitelabel = !!whitelabelGuid;
  const displayGuid = whitelabelGuid || "<your-white-label-id-will-be-added-here>";

  const getOAuth2Url = () => `
// Function to initiate OAuth2 flow
const initiateOAuth2Flow = async () => {
  // Get the auth URL from Airweave's backend
  const response = await fetch(\`https://api.airweave.ai/connections/oauth2/white-label/${displayGuid}/auth_url\`);
  const authUrl = await response.text();

  // Redirect the user to the authorization URL
  window.location.href = authUrl;
};

// Use this function in your button onClick handler:
<button onClick={initiateOAuth2Flow}>Connect to Service</button>
`.trim();

  const getCodeSnippet = () => `
// Add this script to your callback page
const airweaveOAuth = {
  init: async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
      try {
        const response = await fetch('https://api.airweave.ai/connections/oauth2/white-label/${displayGuid}/code', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ code })
        });

        const data = await response.json();
        console.log('Airweave connection created:', data);
      } catch (error) {
        console.error('Error creating connection with Airweave:', error);
      }
    }
  }
};

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', airweaveOAuth.init);
`.trim();

  const handleCopyCode = (code: string, type: 'auth' | 'implementation') => {
    navigator.clipboard.writeText(code);

    if (type === 'auth') {
      setCopiedAuth(true);
      setTimeout(() => setCopiedAuth(false), 1500);
    } else {
      setCopiedImplementation(true);
      setTimeout(() => setCopiedImplementation(false), 1500);
    }

    toast({
      title: "Copied to clipboard",
      description: `The ${type === 'auth' ? 'OAuth2' : 'implementation'} code snippet has been copied to your clipboard.`,
    });
  };

  return (
    <div className={`space-y-6 ${!hasWhitelabel ? "opacity-50" : ""}`}>
      <div className="space-y-6">
        <h2 className="text-xl font-semibold">Integration Code Snippets</h2>

        {/* Tabs */}
        <div className="flex space-x-1 p-1 rounded-md mb-4 w-fit bg-muted border">
          <Button
            variant={activeTab === "auth" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("auth")}
            className={cn(
              "rounded-sm text-xs flex items-center gap-2",
              activeTab === "auth"
                ? "shadow-sm bg-muted"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Terminal className="h-4 w-4" />
            <span>OAuth2 Authorization</span>
          </Button>
          <Button
            variant={activeTab === "implementation" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("implementation")}
            className={cn(
              "rounded-sm text-xs flex items-center gap-2",
              activeTab === "implementation"
                ? "shadow-sm bg-muted"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M13.325 3.05L8.66 20.075C8.57 20.425 8.86 20.75 9.22 20.675L13.05 20.15C13.35 20.1 13.575 19.825 13.575 19.525V3.575C13.575 3.225 13.275 2.975 12.95 3.05C12.825 3.075 12.7 3.075 12.575 3.1L9.22 3.575C8.925 3.625 8.7 3.9 8.7 4.2V15.825C8.7 16.175 9.025 16.4 9.35 16.325C9.35 16.325 10.7 16.025 11.725 15.825C12.75 15.625 13.275 16.325 13.275 16.325" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M19.325 6.325C19.325 5.55 18.775 5 18 5H15.75C15.75 5 16.1 6.325 15.2 6.325C14.35 6.325 10.775 6.325 10.775 6.325C10 6.325 9.44995 6.875 9.44995 7.65V14.35C9.44995 15.125 10 15.675 10.775 15.675H18C18.775 15.675 19.325 15.125 19.325 14.35V6.325Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span>Callback Implementation</span>
          </Button>
        </div>

        {/* Auth URL Tab Content */}
        {activeTab === "auth" && (
          <div className="space-y-4">
            <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
              <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
                <div className="flex items-center gap-3">
                  <Badge className="bg-blue-600 hover:bg-blue-600 text-white text-xs font-bold px-2 rounded">JS</Badge>
                  <span className="text-sm font-medium">OAuth2 Authorization URL Generator</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
                    <span className="font-medium">JavaScript</span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                    onClick={() => handleCopyCode(getOAuth2Url(), 'auth')}
                    disabled={!hasWhitelabel}
                  >
                    {copiedAuth ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
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
                  {getOAuth2Url()}
                </SyntaxHighlighter>
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              <p>This function retrieves an OAuth2 authorization URL and redirects the user to authorize your application.</p>
              <p className="mt-1">Call this function when the user clicks a button to connect their account to your service.</p>
            </div>
          </div>
        )}

        {/* Implementation Code Tab Content */}
        {activeTab === "implementation" && (
          <div className="space-y-4">
            <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
              <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
                <div className="flex items-center gap-3">
                  <Badge className="bg-blue-600 hover:bg-blue-600 text-white text-xs font-bold px-2 rounded">JS</Badge>
                  <span className="text-sm font-medium">Callback Page Implementation</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
                    <span className="font-medium">JavaScript</span>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                    onClick={() => handleCopyCode(getCodeSnippet(), 'implementation')}
                    disabled={!hasWhitelabel}
                  >
                    {copiedImplementation ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
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
                  {getCodeSnippet()}
                </SyntaxHighlighter>
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              <p>Add this code to your callback page that handles the OAuth2 response.</p>
              <p className="mt-1">This script automatically extracts the authorization code and completes the connection with Airweave.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
