import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { Loader2, CreditCard, AlertCircle, Check, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

export default function BillingSetup() {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const { currentOrganization, billingInfo, fetchBillingInfo } = useOrganizationStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);

  const isDark = resolvedTheme === 'dark';

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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary/60" />
      </div>
    );
  }

  const hasActiveSubscription = billingInfo?.has_active_subscription;
  const needsPaymentMethod = billingInfo?.requires_payment_method && !billingInfo?.payment_method_added;
  const isInitialSetup = !hasActiveSubscription;
  const selectedPlan = billingInfo?.plan || 'developer';

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header with logo */}
        <div className="mb-12 text-center">
          <img
            src={isDark ? "/logo-airweave-darkbg.svg" : "/logo-airweave-lightbg.svg"}
            alt="Airweave"
            className="h-8 w-auto mx-auto mb-2"
            style={{ maxWidth: '180px' }}
          />
          <p className="text-xs text-muted-foreground">
            Build smarter agents
          </p>
        </div>

        {/* Main content */}
        <div className="space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-normal">
              {isInitialSetup ? 'Complete Your Setup' : 'Update Payment Method'}
            </h1>
            <p className="text-muted-foreground">
              {isInitialSetup
                ? 'Add a payment method to activate your subscription'
                : 'Update your payment method to continue using Airweave'}
            </p>
          </div>

          {/* Status Alert */}
          {billingInfo?.status === 'past_due' && (
            <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-lg p-4">
              <div className="flex gap-3">
                <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800 dark:text-amber-200">
                  <p className="font-medium mb-1">Payment failed</p>
                  <p>Your last payment failed. Please update your payment method to continue.</p>
                </div>
              </div>
            </div>
          )}

          {/* Plan Details */}
          <div className="border border-border/50 rounded-lg p-6 space-y-4">
            <div className="space-y-1">
              <h3 className="text-lg font-normal">
                {selectedPlan === 'startup' ? 'Startup' : 'Developer'} Plan
              </h3>
              <p className="text-sm text-muted-foreground">
                {selectedPlan === 'startup'
                  ? 'For growing teams with higher demands'
                  : 'Perfect for small teams and projects'}
              </p>
            </div>

            <div className="space-y-3">
              {selectedPlan === 'startup' ? (
                <>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">$299 per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">50 source connections</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">1M entities per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">15-minute sync frequency</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Up to 20 team members</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">14-day free trial, then $89/month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">10 source connections</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">100K entities per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Hourly sync frequency</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Up to 5 team members</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Action Button */}
          <div className="pt-4">
            {hasActiveSubscription && billingInfo?.status === 'past_due' ? (
              <button
                onClick={handleManageSubscription}
                disabled={isLoading}
                className={cn(
                  "w-full flex items-center justify-center space-x-2 px-6 py-3 rounded-lg transition-all",
                  "bg-primary text-primary-foreground hover:bg-primary/90",
                  isLoading && "opacity-50 cursor-not-allowed"
                )}
              >
                <span>Update Payment Method</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <div className="w-full flex justify-center">
                <button
                  onClick={handleSetupPayment}
                  disabled={isLoading}
                  className={cn(
                    "flex items-center justify-center space-x-2 px-6 py-3 rounded-lg transition-all",
                    "bg-primary text-primary-foreground hover:bg-primary/90",
                    isLoading && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {isLoading ? (
                    <>
                      <span>Setting up payment</span>
                      <Loader2 className="w-4 h-4 animate-spin" />
                    </>
                  ) : (
                    <>
                      <span>{isInitialSetup ? 'Complete Setup' : 'Update Payment Method'}</span>
                      <ChevronRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
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
        </div>
      </div>
    </div>
  );
}
