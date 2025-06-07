import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '@/components/ui/select';
import {
  Crown, Shield, Users, X, Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

// Member interfaces
interface Member {
  id: string;
  email: string;
  name: string;
  role: string;
  status: 'active' | 'pending';
  avatar?: string;
}

interface PendingInvitation {
  id: string;
  email: string;
  role: string;
  invited_at: string;
  status: 'pending' | 'expired';
}

interface Organization {
  id: string;
  name: string;
  description?: string;
  role: string;
}

interface MembersSettingsProps {
  currentOrganization: Organization;
}

// Dummy data for members
const DUMMY_MEMBERS: Member[] = [
  {
    id: '1',
    email: 'john@acme.com',
    name: 'John Doe',
    role: 'owner',
    status: 'active',
  },
  {
    id: '2',
    email: 'jane@acme.com',
    name: 'Jane Smith',
    role: 'admin',
    status: 'active',
  }
];

const DUMMY_INVITATIONS: PendingInvitation[] = [
  {
    id: '1',
    email: 'bob@example.com',
    role: 'member',
    invited_at: '2024-01-15T10:00:00Z',
    status: 'pending',
  }
];

export const MembersSettings = ({ currentOrganization }: MembersSettingsProps) => {
  const [members, setMembers] = useState<Member[]>(DUMMY_MEMBERS);
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>(DUMMY_INVITATIONS);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [isInviting, setIsInviting] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [emailValidationTimeout, setEmailValidationTimeout] = useState<NodeJS.Timeout | null>(null);

  const handleInvite = async () => {
    if (!inviteEmail || emailError) return;

    try {
      setIsInviting(true);

      const newInvitation: PendingInvitation = {
        id: Date.now().toString(),
        email: inviteEmail,
        role: inviteRole,
        invited_at: new Date().toISOString(),
        status: 'pending',
      };

      setPendingInvitations(prev => [...prev, newInvitation]);
      setInviteEmail('');
      setInviteRole('member');
      toast.success('Invitation sent successfully');

    } catch (error) {
      console.error('Failed to send invitation:', error);
      toast.error('Failed to send invitation');
    } finally {
      setIsInviting(false);
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

  // Email validation function
  const validateEmail = (email: string) => {
    if (!email) {
      setEmailError('');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setEmailError('Please enter a valid email address');
    } else {
      setEmailError('');
    }
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const email = e.target.value;
    setInviteEmail(email);

    // Clear existing timeout
    if (emailValidationTimeout) {
      clearTimeout(emailValidationTimeout);
    }

    // Check if email is valid immediately
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (email && emailRegex.test(email)) {
      // Immediately clear error if email is valid
      setEmailError('');
    } else if (email) {
      // Wait longer before showing error for invalid emails
      const timeout = setTimeout(() => validateEmail(email), 1500);
      setEmailValidationTimeout(timeout);
    } else {
      // Clear error if email is empty
      setEmailError('');
    }
  };

  const handleEmailBlur = () => {
    validateEmail(inviteEmail);
  };

  const isValidEmail = inviteEmail && !emailError;
  const canEdit = ['owner', 'admin'].includes(currentOrganization.role);

  return (
    <div className="space-y-8">
      {/* Invite Members */}
      {canEdit && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-foreground">Invite new member</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Send an invitation to add a member to your organization
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  type="email"
                  placeholder="Email address"
                  value={inviteEmail}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  className={cn(
                    "h-8 text-sm border-border focus:border-border transition-colors placeholder:text-muted-foreground/60",
                    emailError && inviteEmail && "border-destructive/50"
                  )}
                />
                {emailError && inviteEmail && (
                  <p className="text-xs text-destructive/80 mt-1">{emailError}</p>
                )}
              </div>
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger className="w-32 h-8 text-sm border-border focus:border-border transition-colors">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={handleInvite}
                disabled={isInviting || !isValidEmail}
                size="sm"
                className="h-8 px-4 text-sm bg-primary hover:bg-primary/90 text-white"
              >
                {isInviting ? (
                  <>
                    <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    Send invite
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Pending Invitations */}
      {pendingInvitations.length > 0 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-foreground">Pending invitations</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Invitations that haven't been accepted yet
            </p>
          </div>
          <div className="border border-border rounded-lg divide-y divide-border">
            {pendingInvitations.map((invitation) => (
              <div key={invitation.id} className="flex items-center justify-between py-3 px-4">
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="text-sm font-medium">{invitation.email}</div>
                    <div className="text-xs text-muted-foreground">
                      Invited {new Date(invitation.invited_at).toLocaleDateString()}
                    </div>
                  </div>
                  <Badge variant="outline" className="text-xs opacity-70">
                    {invitation.role}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    Pending
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                    onClick={() => setPendingInvitations(prev => prev.filter(i => i.id !== invitation.id))}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Members */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Members</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            People with access to this organization
          </p>
        </div>

        <div className="space-y-2">
          {members.map((member) => (
            <div key={member.id} className="flex items-center justify-between py-3 px-3 border border-border rounded-md">
              <div className="flex items-center gap-3">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={member.avatar} />
                  <AvatarFallback className="text-xs">
                    {member.name.split(' ').map(n => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <div className="text-sm font-medium">{member.name}</div>
                  <div className="text-xs text-muted-foreground">{member.email}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={getRoleBadgeVariant(member.role)} className="text-xs opacity-70">
                  <span className="flex items-center gap-1">
                    {getRoleIcon(member.role)}
                    {member.role}
                  </span>
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
