import { useEffect, useState } from "react";
import { AuthProviderButton } from "@/components/dashboard";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";
import { DialogFlow } from "@/components/shared/DialogFlow";

export const AuthProviderTable = () => {
    // Use auth providers store
    const {
        authProviders,
        authProviderConnections,
        isLoading: isLoadingAuthProviders,
        isLoadingConnections,
        fetchAuthProviders,
        fetchAuthProviderConnections,
        isAuthProviderConnected,
        getConnectionForProvider
    } = useAuthProvidersStore();

    // Dialog state
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedAuthProvider, setSelectedAuthProvider] = useState<any>(null);

    // Fetch auth providers and connections on component mount
    useEffect(() => {
        // Fetch both auth providers and connections in parallel
        Promise.all([
            fetchAuthProviders(),
            fetchAuthProviderConnections()
        ]).then(([providers, connections]) => {
            console.log(`🔄 [AuthProviderTable] Auth providers loaded: ${providers.length} providers, ${connections.length} connections`);
        });
    }, [fetchAuthProviders, fetchAuthProviderConnections]);

    const handleAuthProviderClick = (authProvider: any) => {
        const isConnected = isAuthProviderConnected(authProvider.short_name);
        const connection = getConnectionForProvider(authProvider.short_name);

        if (isConnected && connection) {
            alert(`Auth provider "${authProvider.name}" is already connected as "${connection.name}"`);
        } else {
            // Open dialog for connecting to auth provider
            setSelectedAuthProvider(authProvider);
            setDialogOpen(true);
        }
    };

    const handleDialogComplete = (result: any) => {
        console.log("Auth provider connection completed:", result);
        setDialogOpen(false);
        setSelectedAuthProvider(null);
    };

    if (isLoadingAuthProviders || isLoadingConnections) {
        return (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 auto-rows-fr">
                {Array.from({ length: 8 }).map((_, index) => (
                    <div
                        key={index}
                        className="h-20 flex items-center justify-center animate-pulse"
                    >
                        <div className="flex flex-col items-center">
                            <div className="h-8 w-8 bg-gray-200 dark:bg-gray-700 rounded-md mb-2"></div>
                            <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    if (authProviders.length === 0) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                <p className="text-lg mb-2">No auth providers found</p>
                <p className="text-sm">Auth providers will appear here when available.</p>
            </div>
        );
    }

    return (
        <>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 auto-rows-fr">
                {authProviders.map((authProvider) => (
                    <AuthProviderButton
                        key={authProvider.id}
                        id={authProvider.id}
                        name={authProvider.name}
                        shortName={authProvider.short_name}
                        isConnected={isAuthProviderConnected(authProvider.short_name)}
                        onClick={() => handleAuthProviderClick(authProvider)}
                    />
                ))}
            </div>

            {/* Dialog for connecting to auth provider */}
            <DialogFlow
                isOpen={dialogOpen}
                onOpenChange={setDialogOpen}
                mode="auth-provider"
                authProviderId={selectedAuthProvider?.id}
                authProviderName={selectedAuthProvider?.name}
                authProviderShortName={selectedAuthProvider?.short_name}
                authProviderAuthType={selectedAuthProvider?.auth_type}
                onComplete={handleDialogComplete}
                dialogId="auth-provider-connection"
            />
        </>
    );
};
