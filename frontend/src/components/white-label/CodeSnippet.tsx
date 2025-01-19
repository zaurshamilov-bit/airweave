import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface CodeSnippetProps {
  whitelabelGuid: string;
  frontendUrl?: string;
  clientId?: string;
  source?: string;
}

export const CodeSnippet = ({ whitelabelGuid, frontendUrl, clientId, source }: CodeSnippetProps) => {
  const { toast } = useToast();
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
    // <button onClick={initiateOAuth2Flow}>Connect to Service</button>
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

  const copyToClipboard = async (content: string, type: 'implementation' | 'oauth2') => {
    await navigator.clipboard.writeText(content);
    toast({
      title: "Copied to clipboard",
      description: `The ${type === 'implementation' ? 'implementation' : 'OAuth2'} code snippet has been copied to your clipboard.`,
    });
  };

  return (
    <div className={`space-y-4 ${!hasWhitelabel ? "opacity-50" : ""}`}>
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">OAuth2 Flow</h2>
        <div className="bg-secondary/10 p-4 rounded-lg space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Authorization URL Generator</h3>
            {hasWhitelabel && (
              <Button variant="outline" size="sm" onClick={() => copyToClipboard(getOAuth2Url(), 'oauth2')}>
                <Copy className="h-4 w-4 mr-2" />
                Copy OAuth2 Code
              </Button>
            )}
          </div>
          <pre className="bg-background p-4 rounded-lg overflow-x-auto">
            <code className="text-sm">{getOAuth2Url()}</code>
          </pre>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Implementation Code</h2>
        <div className="bg-secondary/10 p-4 rounded-lg space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Integration Code</h3>
            {hasWhitelabel && (
              <Button variant="outline" size="sm" onClick={() => copyToClipboard(getCodeSnippet(), 'implementation')}>
                <Copy className="h-4 w-4 mr-2" />
                Copy Implementation
              </Button>
            )}
          </div>
          <pre className="bg-background p-4 rounded-lg overflow-x-auto">
            <code className="text-sm">{getCodeSnippet()}</code>
          </pre>
        </div>
      </div>
    </div>
  );
};