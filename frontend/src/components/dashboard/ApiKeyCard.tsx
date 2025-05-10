import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Copy, Key } from "lucide-react";
import { toast } from "sonner";

interface ApiKeyCardProps {
  apiKey: {
    key_prefix: string;
    plain_key?: string;
  } | null;
  onRequestNewKey?: () => void;
}

export const ApiKeyCard = ({ apiKey, onRequestNewKey }: ApiKeyCardProps) => {
  const [copySuccess, setCopySuccess] = useState(false);

  const handleCopyApiKey = () => {
    if (apiKey?.plain_key) {
      navigator.clipboard.writeText(apiKey.plain_key);
      setCopySuccess(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="p-5">
        <div className="flex items-center mb-1">
          <Key className="h-4 w-4 mr-1.5 text-muted-foreground" />
          <h3 className="text-sm font-medium">API Key</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">Store your API keys securely away</p>
        <div className="flex items-center">
          <Input
            value={apiKey?.plain_key || `tc-${Array(30).fill("*").join("")}0007`}
            className="text-xs font-mono h-9 bg-muted border-border"
            readOnly
          />
          <Button
            variant="ghost"
            size="icon"
            className="ml-1 h-9 w-9"
            onClick={handleCopyApiKey}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="mt-2 text-right">
          <button
            className="text-xs text-primary hover:underline"
            onClick={onRequestNewKey}
          >
            Need another API key?
          </button>
        </div>
      </div>
    </div>
  );
};

export default ApiKeyCard;
