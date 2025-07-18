import { useEffect } from "react";
import { AuthProviderButton } from "@/components/dashboard";
import { useAuthProvidersStore } from "@/lib/stores/authProviders";

export const AuthProviderTable = () => {
    // Use auth providers store
    const { authProviders, isLoading: isLoadingAuthProviders, fetchAuthProviders } = useAuthProvidersStore();

    // Fetch auth providers on component mount
    useEffect(() => {
        fetchAuthProviders().then(authProviders => {
            console.log(`🔄 [AuthProviderTable] Auth providers loaded: ${authProviders.length} auth providers available`);
        });
    }, [fetchAuthProviders]);

    const handleAuthProviderClick = (authProvider: any) => {
        alert("hello");
    };

    if (isLoadingAuthProviders) {
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
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 auto-rows-fr">
            {authProviders.map((authProvider) => (
                <AuthProviderButton
                    key={authProvider.id}
                    id={authProvider.id}
                    name={authProvider.name}
                    shortName={authProvider.short_name}
                    onClick={() => handleAuthProviderClick(authProvider)}
                />
            ))}
        </div>
    );
};
