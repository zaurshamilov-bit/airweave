import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  CreditCard,
  Calendar,
  AlertCircle,
  ExternalLink,
  CheckCircle,
  Clock,
  XCircle,
  Zap,
  Users,
  Database,
  RefreshCw,
  ArrowUpCircle,
  ArrowDownCircle
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { format } from 'date-fns';

interface SubscriptionInfo {
  plan: string;
  status: string;
  trial_ends_at?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  limits: {
    source_connections: number;
    entities_per_month: number;
    sync_frequency_minutes: number;
    team_members: number;
  };
  is_oss: boolean;
  has_active_subscription: boolean;
  grace_period_ends_at?: string;
  pending_plan_change?: string;
  pending_plan_change_at?: string;
}

interface BillingSettingsProps {
  organizationId: string;
}

export const BillingSettings = ({ organizationId }: BillingSettingsProps) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false);
  const [isPortalLoading, setIsPortalLoading] = useState(false);
  const [isCancelLoading, setIsCancelLoading] = useState(false);
  const [isReactivateLoading, setIsReactivateLoading] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  useEffect(() => {
    fetchSubscription();
  }, [organizationId]);

  useEffect(() => {
    // Check for success param from checkout
    if (searchParams.get('success') === 'true') {
      toast.success('Payment method added successfully! Your subscription is now active.');
      // Remove the success param from URL
      searchParams.delete('success');
      setSearchParams(searchParams);
    }
  }, []); // Only run once on mount

  const fetchSubscription = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.get('/billing/subscription');
      if (response.ok) {
        const data = await response.json();
        setSubscription(data);
      } else {
        throw new Error('Failed to fetch subscription');
      }
    } catch (error) {
      console.error('Error fetching subscription:', error);
      toast.error('Failed to load billing information');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpgrade = async (plan: 'developer' | 'startup') => {
    try {
      setIsCheckoutLoading(true);

      // Check if this is a plan change for existing subscription
      if (subscription?.has_active_subscription && subscription.plan !== 'trial') {
        const response = await apiClient.post('/billing/update-plan', { plan });

        if (response.ok) {
          const data = await response.json();
          // Check if we got a checkout URL (for trial upgrades)
          if (data.message && data.message.includes('checkout at:')) {
            // Extract URL from message
            const urlMatch = data.message.match(/checkout at: (.+)$/);
            if (urlMatch && urlMatch[1]) {
              window.location.href = urlMatch[1];
            } else {
              throw new Error('Failed to get checkout URL');
            }
          } else {
            // Normal update succeeded
            toast.success(data.message);
            await fetchSubscription(); // Refresh subscription info
          }
        } else {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to update plan');
        }
      } else {
        // New subscription - redirect to checkout
        const response = await apiClient.post('/billing/checkout-session', {
          plan,
          success_url: `${window.location.origin}/organization/settings?tab=billing&success=true`,
          cancel_url: `${window.location.origin}/organization/settings?tab=billing`
        });

        if (response.ok) {
          const { checkout_url } = await response.json();
          window.location.href = checkout_url;
        } else {
          throw new Error('Failed to create checkout session');
        }
      }
    } catch (error) {
      console.error('Error with subscription change:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to process subscription change');
    } finally {
      setIsCheckoutLoading(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      setIsPortalLoading(true);
      const response = await apiClient.post('/billing/portal-session', {
        return_url: `${window.location.origin}/organization/settings?tab=billing`
      });

      if (response.ok) {
        const { portal_url } = await response.json();
        window.location.href = portal_url;
      } else {
        throw new Error('Failed to create portal session');
      }
    } catch (error) {
      console.error('Error creating portal session:', error);
      toast.error('Failed to open billing portal');
    } finally {
      setIsPortalLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    try {
      setIsCancelLoading(true);
      const response = await apiClient.post('/billing/cancel', {
        immediate: false // Always cancel at period end
      });

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription(); // Refresh subscription info
        setShowCancelDialog(false);
      } else {
        throw new Error('Failed to cancel subscription');
      }
    } catch (error) {
      console.error('Error canceling subscription:', error);
      toast.error('Failed to cancel subscription');
    } finally {
      setIsCancelLoading(false);
    }
  };

  const handleReactivateSubscription = async () => {
    try {
      setIsReactivateLoading(true);
      const response = await apiClient.post('/billing/reactivate');

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription(); // Refresh subscription info
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reactivate subscription');
      }
    } catch (error) {
      console.error('Error reactivating subscription:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reactivate subscription');
    } finally {
      setIsReactivateLoading(false);
    }
  };

  const handleCancelPlanChange = async () => {
    try {
      setIsCancelLoading(true);
      const response = await apiClient.post('/billing/cancel-plan-change');

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription(); // Refresh subscription info
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to cancel plan change');
      }
    } catch (error) {
      console.error('Error canceling plan change:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to cancel plan change');
    } finally {
      setIsCancelLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-500/10 text-green-500 border-green-500/20">
          <CheckCircle className="w-3 h-3 mr-1" />
          Active
        </Badge>;
      case 'trialing':
        return <Badge variant="default" className="bg-blue-500/10 text-blue-500 border-blue-500/20">
          <Clock className="w-3 h-3 mr-1" />
          Trial
        </Badge>;
      case 'past_due':
        return <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Past Due
        </Badge>;
      case 'canceled':
        return <Badge variant="secondary">
          <XCircle className="w-3 h-3 mr-1" />
          Canceled
        </Badge>;

      case 'trial_expired':
        return <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Trial Expired
        </Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getPlanDisplayName = (plan: string) => {
    switch (plan) {
      case 'trial':
        return 'Free Trial';
      case 'developer':
        return 'Developer';
      case 'startup':
        return 'Startup';
      case 'enterprise':
        return 'Enterprise';
      default:
        return plan;
    }
  };

  const isPlanUpgrade = (currentPlan: string, targetPlan: string) => {
    const planHierarchy: Record<string, number> = {
      trial: 0,
      developer: 1,
      startup: 2,
      enterprise: 3
    };
    return planHierarchy[targetPlan] > planHierarchy[currentPlan];
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!subscription) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Unable to load billing information. Please try again later.
        </AlertDescription>
      </Alert>
    );
  }

  const isOnTrial = subscription.plan === 'trial';
  const hasActiveSubscription = subscription.has_active_subscription;
  const canCancel = hasActiveSubscription && !subscription.cancel_at_period_end;
  const canReactivate = subscription.cancel_at_period_end && subscription.current_period_end;

  // Check if this is initial setup (grace period without subscription)
  const isInitialSetup = !hasActiveSubscription && subscription.status === 'trialing';
  const needsSetup = isInitialSetup || subscription.status === 'trial_expired';

  // If this is initial setup or expired trial, show setup prompt
  if (needsSetup) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Billing Setup Required</CardTitle>
                <CardDescription>
                  Complete your billing setup to activate your subscription
                </CardDescription>
              </div>
              {getStatusBadge(subscription.status)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Please complete your billing setup to start using this organization.
              </AlertDescription>
            </Alert>

            <div className="rounded-lg border p-4">
              <h3 className="mb-3 font-semibold">
                {subscription.plan === 'startup' ? 'Startup' : 'Developer'} Plan Selected
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Source Connections</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.limits.source_connections === -1 ? 'Unlimited' : subscription.limits.source_connections}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Entities/Month</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.limits.entities_per_month === -1 ? 'Unlimited' : subscription.limits.entities_per_month.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Sync Frequency</p>
                      <p className="text-xs text-muted-foreground">
                        Every {subscription.limits.sync_frequency_minutes} minutes
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Team Members</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.limits.team_members === -1 ? 'Unlimited' : subscription.limits.team_members}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <Button
              onClick={() => window.location.href = '/billing/setup'}
              size="lg"
              className="w-full"
            >
              Complete Billing Setup
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Current Plan</CardTitle>
              <CardDescription>
                Manage your subscription and billing
              </CardDescription>
            </div>
            {getStatusBadge(subscription.status)}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-2xl font-semibold">
                {getPlanDisplayName(subscription.plan)}
              </h3>
              {subscription.status === 'trialing' && subscription.trial_ends_at && (
                <p className="text-sm text-muted-foreground mt-1">
                  <Calendar className="inline w-3 h-3 mr-1" />
                  Trial ends {format(new Date(subscription.trial_ends_at), 'MMM d, yyyy')}
                </p>
              )}
              {subscription.status === 'canceled' && subscription.current_period_end && (
                <p className="text-sm text-muted-foreground mt-1">
                  <Calendar className="inline w-3 h-3 mr-1" />
                  Access until {format(new Date(subscription.current_period_end), 'MMM d, yyyy')}
                </p>
              )}
              {subscription.pending_plan_change &&
                subscription.pending_plan_change_at &&
                !subscription.cancel_at_period_end && (
                  <div className="mt-2 rounded-md border border-yellow-500/30 bg-yellow-500/10 p-3">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="h-5 w-5 flex-shrink-0 text-yellow-600" />
                      <div className="flex-1">
                        <p className="font-semibold text-yellow-700">Plan Change Scheduled</p>
                        <p className="text-sm text-yellow-600">
                          Your plan will change to{' '}
                          <strong>{getPlanDisplayName(subscription.pending_plan_change)}</strong> on{' '}
                          {format(new Date(subscription.pending_plan_change_at), 'MMM d, yyyy')}.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-yellow-700 hover:bg-yellow-500/20 border-yellow-500/30"
                        onClick={handleCancelPlanChange}
                        disabled={isCancelLoading}
                      >
                        {isCancelLoading ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <>
                            <XCircle className="w-4 h-4 mr-1" />
                            Cancel downgrade
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              {subscription.cancel_at_period_end &&
                subscription.current_period_end && (
                  <Alert className="mt-2">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Your subscription is set to cancel on {format(new Date(subscription.current_period_end), 'MMM d, yyyy')}.
                    </AlertDescription>
                  </Alert>
                )}
            </div>

            <div className="flex gap-2">
              {canReactivate && (
                <Button
                  onClick={handleReactivateSubscription}
                  variant="default"
                  disabled={isReactivateLoading}
                >
                  {isReactivateLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : null}
                  Reactivate
                </Button>
              )}

              {(hasActiveSubscription || subscription.cancel_at_period_end) && (
                <Button
                  onClick={handleManageBilling}
                  variant="outline"
                  disabled={isPortalLoading}
                >
                  {isPortalLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <CreditCard className="w-4 h-4 mr-2" />
                  )}
                  Manage Billing
                </Button>
              )}

              {canCancel && (
                <Button
                  onClick={() => setShowCancelDialog(true)}
                  variant="outline"
                  className="text-destructive"
                >
                  Cancel Subscription
                </Button>
              )}
            </div>
          </div>

          {/* Plan Limits */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Source Connections</p>
                  <p className="text-xs text-muted-foreground">
                    {subscription.limits.source_connections === -1 ? 'Unlimited' : subscription.limits.source_connections}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Entities/Month</p>
                  <p className="text-xs text-muted-foreground">
                    {subscription.limits.entities_per_month === -1 ? 'Unlimited' : subscription.limits.entities_per_month.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Sync Frequency</p>
                  <p className="text-xs text-muted-foreground">
                    Every {subscription.limits.sync_frequency_minutes} minutes
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Team Members</p>
                  <p className="text-xs text-muted-foreground">
                    {subscription.limits.team_members === -1 ? 'Unlimited' : subscription.limits.team_members}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Upgrade Options */}
      {(isOnTrial || subscription.plan === 'developer') && !subscription.cancel_at_period_end && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Available Plans</h3>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Developer Plan */}
            {isOnTrial && (
              <Card>
                <CardHeader>
                  <CardTitle>Developer</CardTitle>
                  <CardDescription>Perfect for small teams and projects</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-3xl font-bold">
                    $89<span className="text-lg font-normal text-muted-foreground">/month</span>
                  </div>
                  <ul className="space-y-2 text-sm">
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      10 source connections
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      100K entities/month
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      Hourly sync frequency
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      5 team members
                    </li>
                  </ul>
                  <Button
                    className="w-full"
                    onClick={() => handleUpgrade('developer')}
                    disabled={isCheckoutLoading}
                  >
                    {isCheckoutLoading ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : null}
                    Upgrade to Developer
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Startup Plan */}
            <Card className={subscription.plan === 'developer' ? 'border-primary' : ''}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Startup</CardTitle>
                    <CardDescription>For growing teams with higher demands</CardDescription>
                  </div>
                  {subscription.plan === 'developer' && (
                    <Badge variant="outline" className="ml-2">
                      <ArrowUpCircle className="w-3 h-3 mr-1" />
                      Upgrade
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-3xl font-bold">
                  $299<span className="text-lg font-normal text-muted-foreground">/month</span>
                </div>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    50 source connections
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    1M entities/month
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    15-min sync frequency
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    20 team members
                  </li>
                </ul>
                <Button
                  className="w-full"
                  onClick={() => handleUpgrade('startup')}
                  disabled={isCheckoutLoading}
                  variant={subscription.plan === 'developer' ? 'default' : 'outline'}
                >
                  {isCheckoutLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : null}
                  {isPlanUpgrade(subscription.plan, 'startup') ? 'Upgrade' : 'Switch'} to Startup
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Enterprise CTA */}
          <Card className="bg-muted/50">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <h4 className="font-semibold">Need more?</h4>
                <p className="text-sm text-muted-foreground">
                  Contact us for custom Enterprise plans with unlimited resources
                </p>
              </div>
              <Button variant="outline" asChild>
                <a href="mailto:sales@airweave.ai">
                  Contact Sales
                  <ExternalLink className="w-4 h-4 ml-2" />
                </a>
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Message when subscription is set to cancel */}
      {subscription.cancel_at_period_end && (subscription.plan === 'developer' || subscription.plan === 'startup') && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Your subscription is set to cancel. Please reactivate your subscription before making any plan changes.
          </AlertDescription>
        </Alert>
      )}

      {/* Downgrade Option for Startup Plan */}
      {subscription.plan === 'startup' && !subscription.cancel_at_period_end && !subscription.pending_plan_change && (
        <Card>
          <CardHeader>
            <CardTitle>Change Plan</CardTitle>
            <CardDescription>Switch to a different plan</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center gap-3">
                <ArrowDownCircle className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="font-medium">Developer Plan</p>
                  <p className="text-sm text-muted-foreground">$89/month • 10 connections • 100K entities</p>
                </div>
              </div>
              <Button
                variant="outline"
                onClick={() => handleUpgrade('developer')}
                disabled={isCheckoutLoading}
              >
                {isCheckoutLoading ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                Downgrade
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Change will take effect at the end of your current billing period
            </p>
          </CardContent>
        </Card>
      )}

      {/* Billing Portal Info */}
      {hasActiveSubscription && (
        <Card className="bg-muted/50">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">
              Access the Stripe customer portal to update payment methods, download invoices, and view your billing history.
              To cancel your subscription, use the cancel button above. Your access will continue until the end of your billing period.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your subscription? Your subscription will remain active until the end of your current billing period.
              {subscription.current_period_end && (
                <p className="mt-2 font-medium">
                  You will have access until {format(new Date(subscription.current_period_end), 'MMMM d, yyyy')}
                </p>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelSubscription}
              disabled={isCancelLoading}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isCancelLoading ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : null}
              Cancel Subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
