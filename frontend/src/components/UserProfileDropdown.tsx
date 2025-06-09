import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { Link } from 'react-router-dom';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuSub,
  DropdownMenuSubContent, DropdownMenuSubTrigger
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ExternalLink, MoreVertical, Building2, Settings,
  UserPlus, Crown, Shield, Users, Plus, LogOut
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { CreateOrganizationModal } from '@/components/organization';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

// Consistent styling for all menu items
const menuItemClass = "flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer";
const subMenuItemClass = "flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer";
const externalLinkClass = "flex items-center justify-between px-2 py-1.5 text-sm";

interface MenuItemWithIconProps {
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}

const MenuItemWithIcon = ({ icon, children, className, onClick, disabled }: MenuItemWithIconProps) => (
  <DropdownMenuItem
    onSelect={onClick}
    disabled={disabled}
    className={cn(menuItemClass, className)}
  >
    <span className="w-4 h-4 flex items-center justify-center text-muted-foreground">
      {icon}
    </span>
    <span className="flex-1">{children}</span>
  </DropdownMenuItem>
);

const ExternalMenuLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <DropdownMenuItem asChild>
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={externalLinkClass}
    >
      <span className="flex items-center gap-2">{children}</span>
      <ExternalLink className="h-3 w-3 opacity-40" />
    </a>
  </DropdownMenuItem>
);

const InternalMenuLink = ({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) => (
  <DropdownMenuItem asChild>
    <Link to={to} className={menuItemClass}>
      <span className="w-4 h-4 flex items-center justify-center text-muted-foreground">
        {icon}
      </span>
      <span className="flex-1">{children}</span>
    </Link>
  </DropdownMenuItem>
);

// Consistent separator component
const MenuSeparator = () => <div className="h-px bg-border/10 my-1" />;

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const {
    organizations,
    currentOrganization,
    fetchUserOrganizations,
    switchOrganization
  } = useOrganizationStore();

  const [firstName, setFirstName] = useState<string>('');
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);
  const [isLoadingOrgs, setIsLoadingOrgs] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    if (user?.name) {
      const nameParts = user.name.split(' ');
      setFirstName(nameParts[0] || '');
    }
  }, [user]);

  // Fetch user organizations when component mounts or user changes
  useEffect(() => {
    const loadOrganizations = async () => {
      if (user) {
        try {
          setIsLoadingOrgs(true);
          await fetchUserOrganizations();
        } catch (error) {
          console.error('Failed to load organizations:', error);
        } finally {
          setIsLoadingOrgs(false);
        }
      }
    };

    loadOrganizations();
  }, [user, fetchUserOrganizations]);

  // Refetch organizations when dropdown opens to ensure fresh data
  useEffect(() => {
    const refreshOrganizations = async () => {
      if (dropdownOpen && user) {
        try {
          setIsLoadingOrgs(true);
          // Always fetch fresh data when dropdown opens
          await fetchUserOrganizations();
        } catch (error) {
          console.error('Failed to refresh organizations:', error);
        } finally {
          setIsLoadingOrgs(false);
        }
      }
    };

    // Only refresh when dropdown opens (becomes true)
    if (dropdownOpen) {
      refreshOrganizations();
    }
  }, [dropdownOpen, user, fetchUserOrganizations]);

  const handleLogout = () => {
    setDropdownOpen(false);
    apiClient.clearToken();
    logout();
  };

  const handleSwitchOrganization = (orgId: string) => {
    switchOrganization(orgId);
    setDropdownOpen(false);
  };

  const handleCreateOrganization = () => {
    setDropdownOpen(false);
    setShowCreateOrgModal(true);
  };

  const handleCreateOrgSuccess = (newOrganization: any) => {
    console.log('Organization created successfully:', newOrganization);
    setShowCreateOrgModal(false);
  };

  const handleCreateOrgModalChange = (open: boolean) => {
    setShowCreateOrgModal(open);
    if (!open) {
      setDropdownOpen(false);
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

  const closeDropdown = () => setDropdownOpen(false);

  return (
    <>
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center justify-between py-2 text-sm rounded-lg w-full hover:bg-muted transition-all duration-200 outline-none focus:outline-none focus:ring-0">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.picture} alt={user?.name || "User"} />
                <AvatarFallback className="bg-primary/10 text-primary text-bold text-xs">
                  {firstName
                    ? firstName[0]
                    : user?.email?.substring(0, 1).toUpperCase() || 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col items-start min-w-0">
                <span className="text-foreground truncate max-w-32">
                  {user?.name || "User"}
                </span>
                {currentOrganization && (
                  <span className="text-xs text-muted-foreground/70 truncate max-w-32">
                    {currentOrganization.name}
                  </span>
                )}
              </div>
            </div>
            <MoreVertical className="h-4 w-4 text-muted-foreground/60" />
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          className="w-[300px] p-1 ml-1 shadow-xs"
          align="end"
          side="top"
          sideOffset={8}
          onEscapeKeyDown={closeDropdown}
          onInteractOutside={closeDropdown}
        >
          {/* User Info Section */}
          <div className="px-2 py-1.5 border-b border-border/10 bg-muted/20">
            <p className="text-sm text-muted-foreground font-medium truncate">
              {user?.email}
            </p>
          </div>

          {/* Organization Switcher */}
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className={cn(subMenuItemClass, "px-2 py-1.5")}>
              <span className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {currentOrganization?.name || 'Select Organization'}
              </span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-72 p-1 shadow-xs animate-none">
              {isLoadingOrgs ? (
                <DropdownMenuItem disabled className="px-2 py-1.5 text-sm text-muted-foreground">
                  Loading organizations...
                </DropdownMenuItem>
              ) : organizations.length > 0 ? (
                <>
                  {organizations.map((org) => (
                    <DropdownMenuItem
                      key={org.id}
                      onSelect={() => handleSwitchOrganization(org.id)}
                      className="flex items-center justify-between px-2 py-1.5"
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <span className="w-4 h-4 flex items-center justify-center">
                          <Building2 className="h-4 w-4 text-muted-foreground" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm truncate">{org.name}</div>
                          {org.is_primary && (
                            <div className="text-xs text-muted-foreground/70">Primary</div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {org.id === currentOrganization?.id && (
                          <div className="w-2 h-2 bg-green-500 rounded-full" />
                        )}
                        <Badge variant={getRoleBadgeVariant(org.role)} className="text-xs scale-90">
                          <span className="flex items-center gap-1">
                            {getRoleIcon(org.role)}
                            {org.role}
                          </span>
                        </Badge>
                      </div>
                    </DropdownMenuItem>
                  ))}

                  <MenuSeparator />

                  <MenuItemWithIcon
                    icon={<Plus className="h-4 w-4" />}
                    onClick={handleCreateOrganization}
                    className="text-primary data-[highlighted]:bg-transparent"
                  >
                    Create Organization
                  </MenuItemWithIcon>
                </>
              ) : (
                <>
                  <DropdownMenuItem disabled className="px-2 py-1.5 text-sm text-muted-foreground">
                    No organizations found
                  </DropdownMenuItem>

                  <MenuSeparator />

                  <MenuItemWithIcon
                    icon={<Plus className="h-4 w-4" />}
                    onClick={handleCreateOrganization}
                    className="text-primary data-[highlighted]:bg-transparent"
                  >
                    Create Organization
                  </MenuItemWithIcon>
                </>
              )}
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          {/* Organization Management */}
          {currentOrganization && ['owner', 'admin'].includes(currentOrganization.role) && (
            <>
              <MenuSeparator />

              <InternalMenuLink
                to="/organization/settings?tab=members"
                icon={<UserPlus className="h-4 w-4" />}
              >
                Invite Members
              </InternalMenuLink>

              <InternalMenuLink
                to="/organization/settings"
                icon={<Settings className="h-4 w-4" />}
              >
                Organization Settings
              </InternalMenuLink>
            </>
          )}

          <MenuSeparator />

          {/* External Links */}
          <ExternalMenuLink href="https://airweave.ai">
            Blog
          </ExternalMenuLink>

          <ExternalMenuLink href="https://docs.airweave.ai">
            Documentation
          </ExternalMenuLink>

          <ExternalMenuLink href="https://discord.gg/484HY9Ehxt">
            Join Discord
          </ExternalMenuLink>

          <MenuSeparator />

          {/* Logout */}
          <MenuItemWithIcon
            icon={<LogOut className="h-4 w-4" />}
            onClick={handleLogout}
            className="text-muted-foreground/80"
          >
            Sign out
          </MenuItemWithIcon>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Create Organization Modal */}
      <CreateOrganizationModal
        open={showCreateOrgModal}
        onOpenChange={handleCreateOrgModalChange}
        onSuccess={handleCreateOrgSuccess}
      />
    </>
  );
}
