import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CreditCard, AlertCircle, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function BillingSetup() {
  const navigate = useNavigate();
  const { currentOrganization, billingInfo, fetchBillingInfo } = useOrganizationStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);

  useEffect(() => {
    // Check current billing status
    checkBillingStatus();
  }, []);

  const checkBillingStatus = async () => {
    setIsCheckingStatus(true);
    try {
      const info = await fetchBillingInfo();

      // If they have an active subscription and payment method, redirect to settings
      if (info && info.has_active_subscription && info.payment_method_added && info.status === 'active') {
        toast.info('You already have an active subscription');
        navigate('/organization/settings?tab=billing');
      }
    } catch (error) {
      console.error('Failed to check billing status:', error);
    } finally {
      setIsCheckingStatus(false);
    }
  };

  const handleSetupPayment = async () => {
    if (!currentOrganization) {
      toast.error('No organization selected');
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiClient.post('/billing/checkout-session', {
        plan: billingInfo?.plan || 'developer', // Use their selected plan or default to developer
        success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/billing/setup`
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const data = await response.json();

      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    } catch (error) {
      console.error('Failed to setup payment:', error);
      toast.error('Failed to setup payment. Please try again.');
      setIsLoading(false);
    }
  };

  const handleManageSubscription = () => {
    navigate('/organization/settings?tab=billing');
  };

  if (isCheckingStatus) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const hasActiveSubscription = billingInfo?.has_active_subscription;
  const needsPaymentMethod = billingInfo?.requires_payment_method && !billingInfo?.payment_method_added;
  const isInitialSetup = !hasActiveSubscription;
  const selectedPlan = billingInfo?.plan || 'developer';

  return (
    <div className="container mx-auto flex h-screen items-center justify-center">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <CreditCard className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">
            {isInitialSetup ? 'Complete Your Setup' : 'Update Payment Method'}
          </CardTitle>
          <CardDescription>
            {isInitialSetup
              ? 'Add a payment method to activate your subscription'
              : 'Update your payment method to continue using Airweave.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Status Alerts */}
          {billingInfo?.status === 'past_due' && (
            <Alert className="border-destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Your last payment failed. Please update your payment method.
              </AlertDescription>
            </Alert>
          )}

          {/* Plan Benefits */}
          <div className="rounded-lg border p-4">
            <h3 className="mb-3 font-semibold">
              {selectedPlan === 'startup' ? 'Startup' : 'Developer'} Plan
            </h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {selectedPlan === 'startup' ? (
                <>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>$299/month</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>Up to 50 source connections</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>1,000,000 entities per month</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>15-minute sync frequency</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>Up to 20 team members</span>
                  </li>
                </>
              ) : (
                <>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>14-day free trial, then $89/month</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>Up to 10 source connections</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>100,000 entities per month</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>Hourly sync frequency</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                    <span>Up to 5 team members</span>
                  </li>
                </>
              )}
            </ul>
          </div>

          {/* Actions */}
          <div className="space-y-3">
            {hasActiveSubscription && billingInfo?.status === 'past_due' ? (
              <Button
                onClick={handleManageSubscription}
                disabled={isLoading}
                className="w-full"
                size="lg"
              >
                Update Payment Method
              </Button>
            ) : (
              <Button
                onClick={handleSetupPayment}
                disabled={isLoading}
                className="w-full"
                size="lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Setting up payment...
                  </>
                ) : isInitialSetup ? (
                  'Complete Setup'
                ) : (
                  'Update Payment Method'
                )}
              </Button>
            )}
          </div>

          {/* Additional Info */}
          <p className="text-center text-xs text-muted-foreground">
            {selectedPlan === 'developer' && isInitialSetup
              ? "You won't be charged during your 14-day trial. Cancel anytime."
              : selectedPlan === 'startup' && isInitialSetup
              ? "Your subscription will start immediately."
              : "Update your payment method to continue your subscription."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
