import { useEffect, useState } from 'react';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Plus, Crown, Shield, Users, Check, Copy, Star
} from 'lucide-react';
import { CreateOrganizationModal } from '@/components/organization';
import { APIKeysSettings } from '@/components/settings/APIKeysSettings';
import { MembersSettings } from '@/components/settings/MembersSettings';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

import { OrganizationSettings } from '@/components/settings/OrganizationSettings';

type TabType = 'settings' | 'api-keys' | 'members';

export const OrganizationSettingsUnified = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const {
    currentOrganization,
    updateOrganization,
    fetchUserOrganizations,
    setPrimaryOrganization
  } = useOrganizationStore();

  // Tab state - get initial tab from URL params
  const initialTab = searchParams.get('tab') as TabType || 'settings';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // General state
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);

  // Add state for copy animation
  const [isCopied, setIsCopied] = useState(false);

  // Add state for primary toggle loading
  const [isPrimaryToggleLoading, setIsPrimaryToggleLoading] = useState(false);

  // Update tab when URL params change
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') as TabType || 'settings';
    setActiveTab(tabFromUrl);
  }, [searchParams]);

  const handleCreateOrgSuccess = (newOrganization: any) => {
    console.log('New organization created from settings:', newOrganization);
  };

  // Enhanced organization update handler that also refreshes organizations list
  const handleOrganizationUpdate = async (id: string, updates: Partial<any>) => {
    // Update the organization in the store
    updateOrganization(id, updates);

    // Refresh the organizations list to ensure all components are updated
    try {
      await fetchUserOrganizations();
    } catch (error) {
      console.error('Failed to refresh organizations after update:', error);
    }
  };

  // Handle primary organization toggle
  const handlePrimaryToggle = async (checked: boolean) => {
    if (!currentOrganization || isPrimaryToggleLoading) return;

    // If unchecking, we don't allow it since there should always be a primary
    if (!checked) {
      toast.error('You must have at least one primary organization');
      return;
    }

    setIsPrimaryToggleLoading(true);

    try {
      const success = await setPrimaryOrganization(currentOrganization.id);

      if (success) {
        toast.success(`${currentOrganization.name} is now your primary organization`);
        // Refresh to ensure UI is in sync
        await fetchUserOrganizations();
      } else {
        toast.error('Failed to set primary organization');
      }
    } catch (error) {
      console.error('Error setting primary organization:', error);
      toast.error('Failed to set primary organization');
    } finally {
      setIsPrimaryToggleLoading(false);
    }
  };

  // Handle copy to clipboard
  const handleCopyId = () => {
    if (currentOrganization?.id) {
      navigator.clipboard.writeText(currentOrganization.id);
      setIsCopied(true);

      // Reset after animation completes
      setTimeout(() => {
        setIsCopied(false);
      }, 1500);

      toast.success('Organization ID copied to clipboard');
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-3 w-3" />;
      case 'admin': return <Shield className="h-3 w-3" />;
      default: return <Users className="h-3 w-3" />;
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner': return 'default';
      case 'admin': return 'secondary';
      default: return 'outline';
    }
  };

  const handleTabChange = (tabId: TabType) => {
    setActiveTab(tabId);
    const newSearchParams = new URLSearchParams(searchParams);
    if (tabId === 'settings') {
      newSearchParams.delete('tab');
    } else {
      newSearchParams.set('tab', tabId);
    }
    navigate(`/organization/settings?${newSearchParams.toString()}`, { replace: true });
  };

  if (!currentOrganization) {
    return (
      <div className="max-w-2xl mx-auto pt-16">
        <div className="text-center">
          <h2 className="text-xl font-medium mb-2">No organization selected</h2>
          <p className="text-muted-foreground text-sm mb-6">
            Select an organization to view settings
          </p>
          <Button
            onClick={() => setShowCreateOrgModal(true)}
            size="sm"
            className="h-8 px-3 text-sm"
          >
            <Plus className="h-3 w-3 mr-1" />
            Create organization
          </Button>
        </div>

        <CreateOrganizationModal
          open={showCreateOrgModal}
          onOpenChange={setShowCreateOrgModal}
          onSuccess={handleCreateOrgSuccess}
        />
      </div>
    );
  }

  const tabs = [
    { id: 'settings' as TabType, label: 'Settings' },
    { id: 'api-keys' as TabType, label: 'API Keys' },
    { id: 'members' as TabType, label: 'Members' }
  ];

  return (
    <>
      <div className="max-w-4xl mx-auto py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div className="flex flex-col">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-xl font-medium">{currentOrganization.name}</h1>
              <Badge variant={getRoleBadgeVariant(currentOrganization.role)} className="text-xs px-2 py-0.5 opacity-70">
                <span className="flex items-center gap-1">
                  {getRoleIcon(currentOrganization.role)}
                  {currentOrganization.role}
                </span>
              </Badge>
              {currentOrganization.is_primary && (
                <Badge variant="outline" className="text-xs px-2 py-0.5 border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  <span className="flex items-center gap-1">
                    <Star className="h-3 w-3" />
                    Primary
                  </span>
                </Badge>
              )}
            </div>

            {/* Organization ID under title like CollectionDetailView */}
            <p className="text-muted-foreground/80 text-xs group relative flex items-center">
              {currentOrganization.id}
              <button
                className="ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-none"
                onClick={handleCopyId}
                title="Copy ID"
              >
                {isCopied ? (
                  <Check className="h-3.5 w-3.5 text-muted-foreground/80 transition-all" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-muted-foreground/80 transition-all" />
                )}
              </button>
            </p>
          </div>

          {/* Primary Organization Toggle */}
          <div className="flex items-center gap-3">
            <div className="flex items-center space-x-3">
              <div className="flex flex-col items-end">
                <label htmlFor="primary-toggle" className="text-sm font-medium text-foreground cursor-pointer">
                  Primary Organization
                </label>
                <p className="text-xs text-muted-foreground">
                  {currentOrganization.is_primary ? 'Default for new resources' : 'Make this your default'}
                </p>
              </div>
              <Switch
                id="primary-toggle"
                checked={currentOrganization.is_primary}
                onCheckedChange={handlePrimaryToggle}
                disabled={isPrimaryToggleLoading}
                className="data-[state=checked]:bg-amber-500 data-[state=checked]:border-amber-500"
              />
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border mb-8">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={cn(
                  "flex items-center gap-2 py-3 px-1 text-sm font-medium transition-colors border-b-2 border-transparent mr-8",
                  isActive
                    ? "text-foreground border-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div>
          {/* Settings Tab */}
          {activeTab === 'settings' && (
            <OrganizationSettings
              currentOrganization={currentOrganization}
              onOrganizationUpdate={handleOrganizationUpdate}
            />
          )}

          {/* API Keys Tab */}
          {activeTab === 'api-keys' && (
            <div>
              <APIKeysSettings />
            </div>
          )}

          {/* Members Tab */}
          {activeTab === 'members' && (
            <MembersSettings
              currentOrganization={currentOrganization}
            />
          )}
        </div>
      </div>

      <CreateOrganizationModal
        open={showCreateOrgModal}
        onOpenChange={setShowCreateOrgModal}
        onSuccess={handleCreateOrgSuccess}
      />
    </>
  );
};
