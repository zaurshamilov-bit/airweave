import { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/auth-context';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { Loader2 } from 'lucide-react';
import authConfig from '@/config/auth';
import { publicPaths } from '@/constants/paths';
import { toast } from 'sonner';

interface AuthGuardProps {
  children: React.ReactNode;
}

export const AuthGuard = ({ children }: AuthGuardProps) => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // This state is crucial to prevent rendering children before the org check is complete
  const [canRenderChildren, setCanRenderChildren] = useState(false);
  const initializationAttempted = useRef(false);

  useEffect(() => {
    // Handle unauthenticated users first
    if (authConfig.authEnabled && !authLoading && !isAuthenticated) {
      // Allow access to login/callback pages without redirecting
      if (location.pathname !== publicPaths.login && location.pathname !== publicPaths.callback) {
        navigate(publicPaths.login, { replace: true });
      }
      return;
    }

    // Start organization check for authenticated users
    if (isAuthenticated && !authLoading && !initializationAttempted.current) {
      initializationAttempted.current = true;

      useOrganizationStore.getState().initializeOrganizations()
        .then(async (fetchedOrganizations) => {
          if (fetchedOrganizations.length > 0) {
            // Check billing status after organizations are loaded
            const billingCheck = await useOrganizationStore.getState().checkBillingStatus();

            // Always allow access - billing issues are handled per-org
            setCanRenderChildren(true);
          } else {
            // User has no orgs, redirect them
            navigate(publicPaths.noOrganization, { replace: true });
          }
        })
        .catch(error => {
          console.error('AuthGuard: Failed to initialize organizations, redirecting.', error);
          navigate(publicPaths.noOrganization, { replace: true });
        });
    }
  }, [isAuthenticated, authLoading, navigate, location.pathname]);

  // Show a loading spinner during the initial auth check or org fetch
  if (!canRenderChildren && (authLoading || (isAuthenticated && !initializationAttempted.current))) {
     // A special check to prevent a flash of the loader on the no-org page
    if (location.pathname === publicPaths.noOrganization) {
      return null;
    }
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Render children ONLY when the check is complete and successful
  if (canRenderChildren) {
    return <>{children}</>;
  }

  // Render nothing while redirecting or for unauthenticated users on public parts of the app
  return null;
};
