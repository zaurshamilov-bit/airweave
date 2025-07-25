import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Users,
  ChevronRight,
  ChevronLeft,
  Check,
  Sparkles,
  Rocket,
  X,
  Code2,
  Database,
  Cloud,
  Shield,
  Cpu,
  Globe,
  Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useAuth } from '@/lib/auth-context';

interface OnboardingData {
  organizationName: string;
  organizationSize: string;
  userRole: string;
  organizationType: string;
  subscriptionPlan: string;
  teamEmails: string[];
}

interface TeamMember {
  email: string;
  role: 'member' | 'admin';
}

const ORGANIZATION_SIZES = [
  { value: '1', label: '1', description: 'Solo' },
  { value: '2-5', label: '2-5', description: 'Small team' },
  { value: '6-20', label: '6-20', description: 'Growing startup' },
  { value: '21-100', label: '21-100', description: 'Scale-up' },
  { value: '101-500', label: '101-500', description: 'Mid-market' },
  { value: '500+', label: '500+', description: 'Enterprise' },
];

const USER_ROLES = [
  { value: 'founder', label: 'Founder/CEO', icon: Sparkles },
  { value: 'engineering', label: 'Engineering', icon: Code2 },
  { value: 'data', label: 'Data/AI', icon: Database },
  { value: 'product', label: 'Product', icon: Rocket },
  { value: 'devops', label: 'DevOps', icon: Cloud },
  { value: 'other', label: 'Other', icon: Users },
];

const ORGANIZATION_TYPES = [
  { value: 'ai_startup', label: 'AI/ML Startup', icon: Cpu, description: 'Building AI-powered products' },
  { value: 'saas', label: 'SaaS Platform', icon: Cloud, description: 'Cloud-based software services' },
  { value: 'data_platform', label: 'Data Platform', icon: Database, description: 'Data infrastructure & analytics' },
  { value: 'dev_tools', label: 'Developer Tools', icon: Code2, description: 'Tools for developers' },
  { value: 'fintech', label: 'Fintech', icon: Shield, description: 'Financial technology' },
  { value: 'other', label: 'Other', icon: Globe, description: 'Other industries' },
];

const SUBSCRIPTION_PLANS = [
  {
    value: 'developer',
    label: 'Developer',
    price: '$89',
    period: 'per month',
    description: 'Perfect for small teams',
    features: [
      '14-day free trial',
      '10 source connections',
      '100K entities/month',
      'Hourly sync',
      '5 team members',
    ],
    teamMemberLimit: 5,
    recommended: true,
    hasTrial: true,
  },
  {
    value: 'startup',
    label: 'Startup',
    price: '$299',
    period: 'per month',
    description: 'For growing companies',
    features: [
      '50 source connections',
      '1M entities/month',
      '15-min sync',
      '20 team members',
      'Priority support',
    ],
    teamMemberLimit: 20,
    recommended: false,
    hasTrial: false,
  },
];

export const Onboarding = () => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const { setCurrentOrganization } = useOrganizationStore();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState<OnboardingData>({
    organizationName: '',
    organizationSize: '',
    userRole: '',
    organizationType: '',
    subscriptionPlan: 'developer', // Default to developer plan
    teamEmails: [],
  });

  // Team invitation specific state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'member' | 'admin'>('member');
  const [emailError, setEmailError] = useState('');
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

  const totalSteps = 6;
  const isDark = resolvedTheme === 'dark';

  // Get the current plan's team member limit
  const currentPlanLimit = SUBSCRIPTION_PLANS.find(
    plan => plan.value === formData.subscriptionPlan
  )?.teamMemberLimit || 2;

  const updateFormData = (field: keyof OnboardingData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    if (currentStep < totalSteps && isStepValid()) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep(prev => prev + 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep(prev => prev - 1);
        setIsTransitioning(false);
      }, 150);
    }
  };

  const handleComplete = async () => {
    // Update formData with team emails
    const emails = teamMembers.map(member => member.email);

    setIsCreating(true);

    try {
      // Step 1: Create organization with metadata
      const org_metadata = {
        onboarding: {
          organizationSize: formData.organizationSize,
          userRole: formData.userRole,
          organizationType: formData.organizationType,
          subscriptionPlan: formData.subscriptionPlan,
          teamInvites: teamMembers, // Store full team member info with roles
          completedAt: new Date().toISOString(),
        }
      };

      const createOrgResponse = await apiClient.post('/organizations', {
        name: formData.organizationName,
        description: `${formData.organizationType} company with ${formData.organizationSize} people`,
        org_metadata,
      });

      if (!createOrgResponse.ok) {
        throw new Error('Failed to create organization');
      }

      const organization = await createOrgResponse.json();

      // Step 2: Update organization context
      setCurrentOrganization(organization);

      // Step 3: Create checkout session for the selected plan
      const checkoutResponse = await apiClient.post('/billing/checkout-session', {
        plan: formData.subscriptionPlan,
        success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/billing/cancel`,
      });

      if (!checkoutResponse.ok) {
        throw new Error('Failed to create billing session');
      }

      const { checkout_url } = await checkoutResponse.json();

      // Step 4: Redirect to Stripe checkout
      window.location.href = checkout_url;

    } catch (error) {
      console.error('Onboarding error:', error);
      toast.error('Failed to complete setup. Please try again.');
      setIsCreating(false);
    }
  };

  // Handle Enter key for progression
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && isStepValid()) {
      e.preventDefault();
      if (currentStep < totalSteps) {
        handleNext();
      } else {
        handleComplete();
      }
    }
  };

  // Auto-progress on selection for button-based steps
  const handleSelection = (field: keyof OnboardingData, value: any) => {
    updateFormData(field, value);
    // Auto-progress for steps 2-5
    if (currentStep >= 2 && currentStep <= 5) {
      setTimeout(() => {
        setIsTransitioning(true);
        setTimeout(() => {
          setCurrentStep(prev => prev + 1);
          setIsTransitioning(false);
        }, 150);
      }, 200); // Small delay for visual feedback
    }
  };

  // Email validation function
  const validateEmail = useCallback((email: string) => {
    if (!email) {
      setEmailError('');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setEmailError('Please enter a valid email address');
      return;
    }

    // Check if email is the current user's email
    if (user?.email && email.toLowerCase() === user.email.toLowerCase()) {
      setEmailError("You don't need to invite yourself - you'll be the owner");
      return;
    }

    // Check if email already exists in team members
    const existingMember = teamMembers.find(member =>
      member.email.toLowerCase() === email.toLowerCase()
    );
    if (existingMember) {
      setEmailError('This email has already been added');
      return;
    }

    // Check team member limit
    if (teamMembers.length >= currentPlanLimit - 1) { // -1 for the owner
      setEmailError(`Your ${formData.subscriptionPlan} plan allows up to ${currentPlanLimit} team members (including you)`);
      return;
    }

    setEmailError('');
  }, [teamMembers, currentPlanLimit, formData.subscriptionPlan, user?.email]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);

    if (!email) {
      setEmailError('');
      return;
    }

    // Basic format check
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailRegex.test(email)) {
      validateEmail(email);
    } else {
      setEmailError('');
    }
  };

  const handleEmailBlur = () => {
    validateEmail(inviteEmail);
  };

  const handleAddTeamMember = () => {
    if (!inviteEmail || emailError) return;

    const newMember: TeamMember = {
      email: inviteEmail,
      role: inviteRole,
    };

    setTeamMembers(prev => [...prev, newMember]);
    setInviteEmail('');
    setInviteRole('member');
    setEmailError('');
  };

  const handleRemoveTeamMember = (email: string) => {
    setTeamMembers(prev => prev.filter(member => member.email !== email));
  };

  const handleTeamEmailKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && inviteEmail && !emailError) {
      e.preventDefault();
      handleAddTeamMember();
    }
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return formData.organizationName.trim().length > 0;
      case 2:
        return formData.organizationSize !== '';
      case 3:
        return formData.userRole !== '';
      case 4:
        return formData.organizationType !== '';
      case 5:
        return formData.subscriptionPlan !== '';
      case 6:
        return true; // Team invites are optional
      default:
        return false;
    }
  };

  const isValidEmail = inviteEmail && !emailError;

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What should we call your organization?</h2>
              <p className="text-muted-foreground">
                Choose a name that represents your team or company
              </p>
            </div>

            <div className="space-y-3">
              <input
                type="text"
                placeholder="e.g., Acme AI"
                value={formData.organizationName}
                onChange={(e) => updateFormData('organizationName', e.target.value)}
                onKeyPress={handleKeyPress}
                className={cn(
                  "w-full px-4 py-3 text-lg bg-transparent border rounded-lg",
                  "focus:outline-none focus:ring-1 focus:ring-primary/50",
                  "placeholder:text-muted-foreground/50"
                )}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                You can always change this later
              </p>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">How many people are in your organization?</h2>
              <p className="text-muted-foreground">
                This helps us recommend the right plan
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {ORGANIZATION_SIZES.map((size) => (
                <button
                  key={size.value}
                  onClick={() => handleSelection('organizationSize', size.value)}
                  className={cn(
                    "p-6 rounded-lg border text-center transition-all",
                    "hover:border-primary/50",
                    formData.organizationSize === size.value
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  )}
                >
                  <div className="text-2xl font-light mb-1">{size.label}</div>
                  <div className="text-xs text-muted-foreground">{size.description}</div>
                </button>
              ))}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What's your role?</h2>
              <p className="text-muted-foreground">
                We'll customize your experience based on your needs
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {USER_ROLES.map((role) => {
                const Icon = role.icon;
                return (
                  <button
                    key={role.value}
                    onClick={() => handleSelection('userRole', role.value)}
                    className={cn(
                      "p-6 rounded-lg border text-center transition-all group",
                      "hover:border-primary/50",
                      formData.userRole === role.value
                        ? "border-primary bg-primary/5"
                        : "border-border"
                    )}
                  >
                    <Icon className={cn(
                      "w-8 h-8 mx-auto mb-3 transition-colors",
                      formData.userRole === role.value
                        ? "text-primary"
                        : "text-muted-foreground group-hover:text-foreground"
                    )} />
                    <div className="text-sm">{role.label}</div>
                  </button>
                );
              })}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">What type of company are you?</h2>
              <p className="text-muted-foreground">
                This helps us understand your data integration needs
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {ORGANIZATION_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <button
                    key={type.value}
                    onClick={() => handleSelection('organizationType', type.value)}
                    className={cn(
                      "p-6 rounded-lg border text-left transition-all group",
                      "hover:border-primary/50",
                      formData.organizationType === type.value
                        ? "border-primary bg-primary/5"
                        : "border-border"
                    )}
                  >
                    <div className="flex items-start space-x-4">
                      <Icon className={cn(
                        "w-6 h-6 mt-0.5 flex-shrink-0 transition-colors",
                        formData.organizationType === type.value
                          ? "text-primary"
                          : "text-muted-foreground group-hover:text-foreground"
                      )} />
                      <div>
                        <div className="font-medium mb-1">{type.label}</div>
                        <div className="text-xs text-muted-foreground">{type.description}</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">Choose your plan</h2>
              <p className="text-muted-foreground">
                You can always upgrade or downgrade later
              </p>
            </div>

            <div className="grid gap-4">
              {SUBSCRIPTION_PLANS.map((plan) => (
                <button
                  key={plan.value}
                  onClick={() => handleSelection('subscriptionPlan', plan.value)}
                  className={cn(
                    "relative p-6 pt-8 rounded-lg border text-left transition-all",
                    "hover:border-primary/50",
                    formData.subscriptionPlan === plan.value
                      ? "border-primary bg-primary/5"
                      : "border-border"
                  )}
                >
                  {plan.recommended && (
                    <div className="absolute top-3 right-6">
                      <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded-full">
                        Recommended
                      </span>
                    </div>
                  )}

                  {plan.hasTrial && (
                    <div className="absolute top-3 left-6">
                      <span className="text-xs bg-green-500/10 text-green-600 dark:text-green-400 px-2 py-0.5 rounded-full">
                        14-day free trial
                      </span>
                    </div>
                  )}

                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-medium text-lg mb-1">{plan.label}</h3>
                      <p className="text-sm text-muted-foreground">{plan.description}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-light">{plan.price}</div>
                      {plan.period && (
                        <div className="text-xs text-muted-foreground">{plan.period}</div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-muted-foreground">
                    {plan.features.map((feature, index) => (
                      <div key={index} className="flex items-center">
                        <Check className="w-3 h-3 mr-2 text-primary flex-shrink-0" />
                        {feature}
                      </div>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>
        );

      case 6:
        return (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-normal">Invite your team</h2>
              <p className="text-muted-foreground">
                Get your team onboard from day one
              </p>
            </div>

            {/* Add team member form */}
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-foreground">Add team members</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Your {formData.subscriptionPlan} plan includes up to {currentPlanLimit} team members
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="flex-1">
                    <input
                      type="email"
                      placeholder="Email address"
                      value={inviteEmail}
                      onChange={handleEmailChange}
                      onBlur={handleEmailBlur}
                      onKeyPress={handleTeamEmailKeyPress}
                      className={cn(
                        "w-full h-8 px-3 text-sm bg-transparent border rounded-md",
                        "focus:outline-none focus:ring-0 focus:border-border",
                        "placeholder:text-muted-foreground/60 transition-colors",
                        emailError && inviteEmail && "border-destructive/50"
                      )}
                    />
                    {emailError && inviteEmail && (
                      <p className="text-xs text-destructive/80 mt-1">{emailError}</p>
                    )}
                  </div>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as 'member' | 'admin')}
                    className={cn(
                      "w-32 h-8 px-3 text-sm bg-transparent border rounded-md",
                      "focus:outline-none focus:ring-0 focus:border-border transition-colors"
                    )}
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    onClick={handleAddTeamMember}
                    disabled={!isValidEmail}
                    className={cn(
                      "h-8 px-4 text-sm rounded-md transition-all",
                      isValidEmail
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "bg-muted text-muted-foreground cursor-not-allowed"
                    )}
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* Team members list */}
              {teamMembers.length > 0 && (
                <div className="space-y-4 mt-6">
                  <div>
                    <h3 className="text-sm font-medium text-foreground">Team members to invite</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {teamMembers.length} of {currentPlanLimit - 1} team members added
                    </p>
                  </div>

                  <div className="border border-border rounded-lg divide-y divide-border">
                    {teamMembers.map((member, index) => (
                      <div key={index} className="flex items-center justify-between py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="text-sm">{member.email}</div>
                          <span className={cn(
                            "text-xs px-2 py-0.5 rounded-full",
                            member.role === 'admin'
                              ? "bg-primary/10 text-primary"
                              : "bg-muted text-muted-foreground"
                          )}>
                            {member.role}
                          </span>
                        </div>
                        <button
                          onClick={() => handleRemoveTeamMember(member.email)}
                          className="p-1 rounded hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-xs text-muted-foreground">
                You can always invite more team members later from your organization settings
              </p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl relative">
        {/* Header with logo branding */}
        <div className="mb-12 text-center">
          <img
            src={isDark ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg"}
            alt="Airweave"
            className="h-8 w-auto mx-auto mb-2"
            style={{ maxWidth: '180px' }}
          />
          <p className="text-xs text-muted-foreground">
            Let agents search any app
          </p>
        </div>

        {/* Progress and close button */}
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center space-x-6">
            {/* Step indicators */}
            <div className="flex items-center space-x-2">
              {Array.from({ length: totalSteps }, (_, i) => (
                <div
                  key={i}
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    i < currentStep
                      ? "w-6 bg-primary"
                      : i === currentStep - 1
                      ? "w-12 bg-primary"
                      : "w-6 bg-muted"
                  )}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              Step {currentStep} of {totalSteps}
            </span>

            <button
              onClick={() => navigate('/')}
              className="p-2 rounded-lg hover:bg-muted/50 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content with fade transition */}
        <div className={cn(
          "min-h-[400px] transition-opacity duration-150",
          isTransitioning ? "opacity-0" : "opacity-100"
        )}>
          {renderStep()}
        </div>

        {/* Actions */}
        <div className="mt-12 flex items-center justify-between">
          <button
            onClick={handleBack}
            disabled={currentStep === 1}
            className={cn(
              "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all",
              currentStep === 1
                ? "opacity-0 pointer-events-none"
                : "hover:bg-muted/50 text-muted-foreground hover:text-foreground"
            )}
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Back</span>
          </button>

          {currentStep < totalSteps ? (
            <button
              onClick={handleNext}
              disabled={!isStepValid()}
              className={cn(
                "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all",
                isStepValid()
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              <span>Continue</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleComplete}
              disabled={!isStepValid() || isCreating}
              className={cn(
                "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all",
                isStepValid() && !isCreating
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              {isCreating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>Complete Setup</span>
                  <Check className="w-4 h-4" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
