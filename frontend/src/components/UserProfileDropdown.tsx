import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useOrganizationStore } from '@/lib/stores/organization-store';
import { Link } from 'react-router-dom';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuSub,
  DropdownMenuSubContent, DropdownMenuSubTrigger
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  ExternalLink, MoreVertical, Building2, Settings,
  UserPlus, Crown, Shield, Users
} from 'lucide-react';
import { apiClient } from '@/lib/api';

// Dummy data for now until backend is ready
const DUMMY_ORGANIZATIONS = [
  {
    id: '1',
    name: 'Acme Corp',
    description: 'Main organization',
    role: 'owner' as const,
    is_primary: true,
  },
  {
    id: '2',
    name: 'Beta Inc',
    description: 'Secondary organization',
    role: 'admin' as const,
    is_primary: false,
  }
];

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const {
    organizations,
    currentOrganization,
    setOrganizations,
    setCurrentOrganization
  } = useOrganizationStore();

  const [firstName, setFirstName] = useState<string>('');

  useEffect(() => {
    if (user?.name) {
      const nameParts = user.name.split(' ');
      setFirstName(nameParts[0] || '');
    }
  }, [user]);

  // Initialize dummy data on mount
  useEffect(() => {
    if (organizations.length === 0) {
      setOrganizations(DUMMY_ORGANIZATIONS);
    }
  }, [organizations.length, setOrganizations]);

  const handleLogout = () => {
    apiClient.clearToken();
    logout();
  };

  const switchOrganization = (orgId: string) => {
    const org = organizations.find(o => o.id === orgId);
    if (org) {
      setCurrentOrganization(org);
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

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center justify-between px-1 py-2 text-sm font-medium rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all duration-200 ease-in-out w-full">
          <div className="flex items-center">
            <Avatar className="h-8 w-8 mr-3">
              <AvatarImage src={user?.picture} alt={user?.name || "User"} />
              <AvatarFallback className="bg-primary/0 border text-primary text-xs">
                {firstName
                  ? firstName[0]
                  : user?.email?.substring(0, 1).toUpperCase() || 'U'}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col items-start">
              <span>{user?.name || "User"}</span>
              {currentOrganization && (
                <span className="text-xs text-muted-foreground truncate max-w-32">
                  {currentOrganization.name}
                </span>
              )}
            </div>
          </div>
          <MoreVertical className="h-4 w-4 opacity-70" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="ml-2 w-[280px] p-0 rounded-md" align="end" side="top" sideOffset={4}>
        {/* User Info Section */}
        <div className="py-2 px-3 border-b border-border/10">
          <p className="text-sm text-muted-foreground truncate">
            {user?.email}
          </p>
          {currentOrganization && (
            <div className="flex items-center gap-2 mt-1">
              <Building2 className="h-3 w-3" />
              <span className="text-xs font-medium">{currentOrganization.name}</span>
              <Badge
                variant={getRoleBadgeVariant(currentOrganization.role)}
                className="text-xs h-4 px-1"
              >
                {getRoleIcon(currentOrganization.role)}
                {currentOrganization.role}
              </Badge>
            </div>
          )}
        </div>

        {/* Organization Switcher */}
        {organizations.length > 1 && (
          <>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger className="px-3 py-1.5 text-sm">
                <Building2 className="h-4 w-4 mr-2" />
                Switch Organization
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-64">
                {organizations.map((org) => (
                  <DropdownMenuItem
                    key={org.id}
                    onSelect={() => switchOrganization(org.id)}
                    disabled={org.id === currentOrganization?.id}
                    className="flex items-center justify-between px-3 py-2"
                  >
                    <div className="flex items-center">
                      <Building2 className="h-4 w-4 mr-2" />
                      <div>
                        <div className="font-medium">{org.name}</div>
                        {org.is_primary && (
                          <div className="text-xs text-muted-foreground">Primary</div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {org.id === currentOrganization?.id && (
                        <div className="w-2 h-2 bg-green-500 rounded-full" />
                      )}
                      <Badge
                        variant={getRoleBadgeVariant(org.role)}
                        className="text-xs h-4 px-1"
                      >
                        {getRoleIcon(org.role)}
                      </Badge>
                    </div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuSeparator className="opacity-10" />
          </>
        )}

        {/* Organization Management */}
        {currentOrganization && ['owner', 'admin'].includes(currentOrganization.role) && (
          <>
            <div className="py-1">
              <DropdownMenuItem asChild>
                <Link to="/organization/members" className="flex items-center px-3 py-1.5 text-sm">
                  <UserPlus className="h-4 w-4 mr-2" />
                  Invite Members
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild>
                <Link to="/organization/settings" className="flex items-center px-3 py-1.5 text-sm">
                  <Settings className="h-4 w-4 mr-2" />
                  Organization Settings
                </Link>
              </DropdownMenuItem>
            </div>
            <DropdownMenuSeparator className="opacity-10" />
          </>
        )}

        {/* External Links */}
        <div className="py-1">
          <DropdownMenuItem asChild>
            <a href="https://airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Blog <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://docs.airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Documentation <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://discord.gg/484HY9Ehxt" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Join Discord community <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        {/* Account Settings */}
        <div className="py-1">
          <DropdownMenuItem asChild>
            <Link to="/settings/account" className="px-3 py-1.5 text-sm">
              Account Settings
            </Link>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        {/* Logout */}
        <div className="py-1">
          <DropdownMenuItem onSelect={handleLogout} className="px-3 py-1.5 text-sm text-muted-foreground">
            Sign out
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
