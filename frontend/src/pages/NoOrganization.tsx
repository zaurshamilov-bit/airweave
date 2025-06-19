import { useAuth } from '@/lib/auth-context';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, Mail, Users } from 'lucide-react';

export const NoOrganization = () => {
  const { logout } = useAuth();

  const handleSignOut = () => {
    logout({ logoutParams: { returnTo: window.location.origin } });
  };

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
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
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
