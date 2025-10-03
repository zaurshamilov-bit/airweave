import React from 'react';
import { Button } from '@/components/ui/button';
import { ExternalLink } from 'lucide-react';
import { useSidePanelStore } from '@/lib/stores/sidePanelStore';

interface OAuthRedirectViewProps {
    context: {
        authenticationUrl?: string;
        sourceName?: string;
        collectionId?: string;
    };
}

export const OAuthRedirectView: React.FC<OAuthRedirectViewProps> = ({ context }) => {
    const { authenticationUrl, sourceName, collectionId } = context;
    const { closePanel } = useSidePanelStore.getState();

    const handleRedirect = () => {
        if (authenticationUrl) {
            // Save collection context to sessionStorage before OAuth redirect
            if (collectionId) {
                const existingStateJson = sessionStorage.getItem('oauth_dialog_state');
                const existingState = existingStateJson ? JSON.parse(existingStateJson) : {};

                const stateToSave = {
                    ...existingState,
                    collectionId: collectionId,
                    originPath: `/collections/${collectionId}`,
                    timestamp: Date.now(),
                };

                sessionStorage.setItem('oauth_dialog_state', JSON.stringify(stateToSave));
            }

            // Close the panel before redirecting
            closePanel();
            window.location.href = authenticationUrl;
        }
    };

    return (
        <div className="p-6 text-center flex flex-col items-center justify-center h-full">
            <div className="p-4 bg-accent rounded-lg mb-6">
                <ExternalLink className="h-10 w-10 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Complete Authentication</h3>
            <p className="text-muted-foreground mb-6">
                You need to authorize Airweave to access your {sourceName} account.
                You'll be redirected to a secure page to continue.
            </p>
            <Button onClick={handleRedirect} className="w-full">
                Continue to {sourceName}
            </Button>
        </div>
    );
};
