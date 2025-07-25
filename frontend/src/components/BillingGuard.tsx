import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, CreditCard } from 'lucide-react';

interface BillingGuardProps {
  children: React.ReactNode;
  requiresActiveBilling?: boolean;
}

export const BillingGuard = ({ children, requiresActiveBilling = true }: BillingGuardProps) => {
  const navigate = useNavigate();
  const { currentOrganization, billingInfo, fetchBillingInfo, billingLoading } = useOrganizationStore();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    checkBilling();
  }, [currentOrganization?.id]);

  const checkBilling = async () => {
    if (!currentOrganization) {
      setIsChecking(false);
      return;
    }

    setIsChecking(true);
    try {
      await fetchBillingInfo();
    } finally {
      setIsChecking(false);
    }
  };

  if (isChecking || billingLoading) {
    return <div className="flex items-center justify-center p-8">Loading billing status...</div>;
  }

  // If billing is not enabled (OSS), allow access
  if (!billingInfo || billingInfo.is_oss) {
    return <>{children}</>;
  }

  const needsPaymentMethod = billingInfo.requires_payment_method;
  const isGracePeriodExpired = billingInfo.grace_period_ends_at &&
    new Date(billingInfo.grace_period_ends_at) <= new Date() &&
    !billingInfo.payment_method_added;

  // Check if subscription is truly inactive (past the current period end)
  const isSubscriptionExpired = billingInfo.current_period_end &&
    new Date(billingInfo.current_period_end) <= new Date();

  // Only consider it inactive if it's canceled AND past the period end
  const isSubscriptionInactive = (billingInfo.status === 'canceled' && isSubscriptionExpired) ||
    billingInfo.status === 'trial_expired';

  // If this component requires active billing and there's an issue, show the appropriate message
  if (requiresActiveBilling && (isGracePeriodExpired || isSubscriptionInactive)) {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-6">
        <div className="text-center max-w-md">
          <CreditCard className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-2xl font-semibold mb-2">Billing Action Required</h2>
          <p className="text-muted-foreground mb-6">
            {isGracePeriodExpired
              ? "Your grace period has expired. Please add a payment method to continue using this organization's resources."
              : "Your subscription has ended. Please reactivate to continue using this organization's resources."}
          </p>
          <Button
            onClick={() => navigate('/billing/setup')}
            size="lg"
          >
            {isGracePeriodExpired ? 'Add Payment Method' : 'Reactivate Subscription'}
          </Button>
        </div>
      </div>
    );
  }

  // Show a warning banner if payment is needed but not critical yet
  const showWarning = needsPaymentMethod && !isGracePeriodExpired && billingInfo.in_grace_period;

  return (
    <>
      {showWarning && (
        <Alert className="mb-4 border-warning">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Payment Method Required</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>
              You have {Math.ceil(
                (new Date(billingInfo.grace_period_ends_at!).getTime() - new Date().getTime()) /
                (1000 * 60 * 60 * 24)
              )} days left to add a payment method for this organization.
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/billing/setup')}
              className="ml-4"
            >
              Add Payment Method
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {children}
    </>
  );
};
