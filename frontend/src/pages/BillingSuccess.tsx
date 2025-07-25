import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, Users } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useAuth0 } from '@auth0/auth0-react';

export const BillingSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { fetchUserOrganizations, currentOrganization } = useOrganizationStore();
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  const [isProcessing, setIsProcessing] = useState(true);
  const [invitesSent, setInvitesSent] = useState(false);
  const [hasProcessed, setHasProcessed] = useState(false);

  useEffect(() => {
    const processSuccess = async () => {
      // Prevent multiple executions
      if (hasProcessed) return;

      // Wait for auth to be ready
      if (authLoading || !isAuthenticated) {
        return;
      }

      setHasProcessed(true);

      try {
        // Wait a moment to ensure auth token is fully available
        await new Promise(resolve => setTimeout(resolve, 500));

        // Refresh organizations to get updated billing status
        await fetchUserOrganizations();

        // Get the current organization with metadata
        if (currentOrganization?.org_metadata?.onboarding?.teamInvites) {
          const invites = currentOrganization.org_metadata.onboarding.teamInvites;

          // Send team invites
          for (const invite of invites) {
            try {
              const response = await apiClient.post(`/organizations/${currentOrganization.id}/invitations`, {
                email: invite.email,
                role: invite.role,
              });

              if (!response.ok) {
                console.error(`Failed to invite ${invite.email}`);
              }
            } catch (error) {
              console.error(`Error inviting ${invite.email}:`, error);
            }
          }

          if (invites.length > 0) {
            setInvitesSent(true);
            toast.success(`Sent ${invites.length} team invitation${invites.length > 1 ? 's' : ''}`);
          }
        }

        // Wait a moment for visual feedback
        setTimeout(() => {
          setIsProcessing(false);
          // Redirect to dashboard after 2 seconds
          setTimeout(() => {
            navigate('/');
          }, 2000);
        }, 1500);

      } catch (error) {
        console.error('Error processing billing success:', error);
        toast.error('Something went wrong. Please contact support.');
        setIsProcessing(false);
      }
    };

    processSuccess();
  }, [authLoading, isAuthenticated, hasProcessed, fetchUserOrganizations, navigate, currentOrganization]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md text-center space-y-8">
        {isProcessing ? (
          <>
            <Loader2 className="w-16 h-16 mx-auto animate-spin text-primary" />
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold">Setting up your account...</h1>
              <p className="text-muted-foreground">
                This will just take a moment
              </p>
            </div>
          </>
        ) : (
          <>
            <CheckCircle className="w-16 h-16 mx-auto text-green-500" />
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold">Welcome to Airweave!</h1>
              <p className="text-muted-foreground">
                Your subscription is active and your trial has begun
              </p>
              {invitesSent && (
                <p className="text-sm text-muted-foreground flex items-center justify-center gap-2 mt-4">
                  <Users className="w-4 h-4" />
                  Team invitations have been sent
                </p>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              Redirecting to your dashboard...
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default BillingSuccess;
