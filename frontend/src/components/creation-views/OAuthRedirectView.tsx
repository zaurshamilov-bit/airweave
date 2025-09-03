import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { ExternalLink, Loader2, Copy, Check, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

export const OAuthRedirectView: React.FC = () => {
  const {
    sourceName,
    authenticationUrl,
    setStep
  } = useCollectionCreationStore();

  const [copied, setCopied] = useState(false);
  const [autoRedirect, setAutoRedirect] = useState(true);

  useEffect(() => {
    // Auto-redirect after a short delay if enabled
    if (authenticationUrl && autoRedirect) {
      const timer = setTimeout(() => {
        window.location.href = authenticationUrl;
      }, 3000);

      return () => clearTimeout(timer);
    }
  }, [authenticationUrl, autoRedirect]);

  const handleConnect = () => {
    if (authenticationUrl) {
      window.location.href = authenticationUrl;
    }
  };

  const handleCopyUrl = async () => {
    if (authenticationUrl) {
      try {
        await navigator.clipboard.writeText(authenticationUrl);
        setCopied(true);
        toast.success('Authentication URL copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        toast.error('Failed to copy URL');
      }
    }
  };

  return (
    <div className="p-8">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setStep('source-config')}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-semibold">Connect to {sourceName}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Authorize access to your {sourceName} account
            </p>
          </div>
        </div>

        {/* OAuth Options */}
        <div className="space-y-4">
          {/* Direct Connection */}
          <div className="p-6 rounded-lg border border-gray-200 dark:border-gray-800 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                <ExternalLink className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium mb-1">Connect Directly</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  You'll be redirected to {sourceName} to authorize access
                </p>
              </div>
            </div>

            <Button onClick={handleConnect} className="w-full">
              <ExternalLink className="w-4 h-4 mr-2" />
              Connect with {sourceName}
            </Button>
          </div>

          {/* Share URL Option */}
          <div className="p-6 rounded-lg border border-gray-200 dark:border-gray-800 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center flex-shrink-0">
                <Copy className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium mb-1">Share Authentication URL</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                  Copy this URL to share with someone who needs to authorize the connection
                </p>

                {/* URL Display */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                    <p className="text-xs font-mono text-gray-600 dark:text-gray-400 break-all">
                      {authenticationUrl || 'Loading...'}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={handleCopyUrl}
                    disabled={!authenticationUrl}
                  >
                    {copied ? (
                      <Check className="w-4 h-4 text-green-600" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-redirect toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
            <div className="flex items-center gap-2">
              {autoRedirect && <Loader2 className="w-4 h-4 animate-spin" />}
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {autoRedirect ? 'Auto-redirecting in 3 seconds...' : 'Auto-redirect disabled'}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAutoRedirect(!autoRedirect)}
            >
              {autoRedirect ? 'Cancel' : 'Enable'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
