import { useAuth } from '@/lib/auth-context';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, Mail, Users, Loader2, Plus } from 'lucide-react';

export const NoOrganization = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [isChecking, setIsChecking] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const handleSignOut = () => {
    logout();
  };

  const handleCreateOrganization = () => {
    navigate('/onboarding');
  };

  const checkForOrganizations = async () => {
    try {
      setIsChecking(true);
      const organizations = await useOrganizationStore.getState().initializeOrganizations();

      if (organizations.length > 0) {
        console.log('Organizations found, redirecting to dashboard');
        navigate('/', { replace: true });
      }
    } catch (error) {
      console.error('Failed to check for organizations:', error);
    } finally {
      setIsChecking(false);
    }
  };

  // Set up periodic checking every 3 seconds
  useEffect(() => {
    // Initial check
    checkForOrganizations();

    // Set up interval for periodic checks
    intervalRef.current = setInterval(checkForOrganizations, 3000);

    // Cleanup interval on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-orange-100 dark:bg-orange-900/20">
            <AlertCircle className="h-8 w-8 text-orange-600 dark:text-orange-400" />
          </div>
          <CardTitle className="text-xl font-semibold">
            No Organization Access
          </CardTitle>
          <CardDescription className="text-center">
            You are not a member of any organization yet.
            {isChecking && (
              <div className="flex items-center justify-center mt-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Checking for access...
              </div>
            )}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <Button
            onClick={handleCreateOrganization}
            className="w-full"
            size="lg"
            disabled={isChecking}
          >
            <Plus className="h-4 w-4 mr-2" />
            Create New Organization
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">Or</span>
            </div>
          </div>

          <div className="flex items-start space-x-3 rounded-lg border p-4">
            <Users className="h-5 w-5 mt-0.5 text-muted-foreground" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium">Join an Existing Organization</p>
              <p className="text-sm text-muted-foreground">
                Please ask an administrator of an existing Airweave organization to send you an invitation.
              </p>
            </div>
          </div>

          <div className="flex items-start space-x-3 rounded-lg border p-4">
            <Mail className="h-5 w-5 mt-0.5 text-muted-foreground" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium">Contact Support</p>
              <p className="text-sm text-muted-foreground">
                If you believe this is an error, please contact our support team for assistance.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t">
            <Button
              variant="outline"
              className="w-full"
              onClick={handleSignOut}
              disabled={isChecking}
            >
              Sign Out
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default NoOrganization;
