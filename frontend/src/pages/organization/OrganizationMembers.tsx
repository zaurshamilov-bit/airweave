import { useState, useEffect } from 'react';
import { useOrganizationStore } from '@/lib/stores/organization-store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '@/components/ui/table';
import { UserPlus, Mail, MoreHorizontal, Crown, Shield, Users } from 'lucide-react';
import { apiClient } from '@/lib/api';

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

// Dummy data for now
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

export const OrganizationMembers = () => {
  const { currentOrganization } = useOrganizationStore();
  const [members, setMembers] = useState<Member[]>(DUMMY_MEMBERS);
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>(DUMMY_INVITATIONS);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [isLoading, setIsLoading] = useState(false);

  const handleInvite = async () => {
    if (!inviteEmail) return;

    try {
      setIsLoading(true);

      // For now, just add to dummy data since API isn't ready
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

      // TODO: Uncomment when API is ready
      // await inviteUser(inviteEmail, inviteRole);

    } catch (error) {
      console.error('Failed to send invitation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-4 w-4" />;
      case 'admin': return <Shield className="h-4 w-4" />;
      default: return <Users className="h-4 w-4" />;
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner': return 'default';
      case 'admin': return 'secondary';
      default: return 'outline';
    }
  };

  if (!currentOrganization) {
    return <div>No organization selected</div>;
  }

  return (
    <div className="container mx-auto py-6 max-w-6xl">
      <div className="flex items-center gap-2 mb-6">
        <Users className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Organization Members</h1>
      </div>

      <div className="grid gap-6">
        {/* Invite Members */}
        {['owner', 'admin'].includes(currentOrganization.role) && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="h-5 w-5" />
                Invite New Member
              </CardTitle>
              <CardDescription>
                Send an invitation to add a new member to your organization.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <div className="flex-1">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="Enter email address"
                  />
                </div>
                <div>
                  <Label htmlFor="role">Role</Label>
                  <Select value={inviteRole} onValueChange={setInviteRole}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="member">Member</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button
                    onClick={handleInvite}
                    disabled={!inviteEmail || isLoading}
                    className="flex items-center gap-2"
                  >
                    <Mail className="h-4 w-4" />
                    {isLoading ? 'Sending...' : 'Send Invite'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Current Members */}
        <Card>
          <CardHeader>
            <CardTitle>Current Members ({members.length})</CardTitle>
            <CardDescription>
              Manage your organization's members and their roles.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={member.avatar} />
                          <AvatarFallback>
                            {member.name?.substring(0, 2).toUpperCase() ||
                             member.email.substring(0, 2).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="font-medium">{member.name || member.email}</div>
                          {member.name && (
                            <div className="text-sm text-muted-foreground">{member.email}</div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={getRoleBadgeVariant(member.role)}
                        className="flex items-center gap-1 w-fit"
                      >
                        {getRoleIcon(member.role)}
                        {member.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={member.status === 'active' ? 'default' : 'secondary'}>
                        {member.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Pending Invitations */}
        {pendingInvitations.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Pending Invitations ({pendingInvitations.length})</CardTitle>
              <CardDescription>
                Invitations that have been sent but not yet accepted.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Invited</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingInvitations.map((invitation) => (
                    <TableRow key={invitation.id}>
                      <TableCell>{invitation.email}</TableCell>
                      <TableCell>
                        <Badge
                          variant={getRoleBadgeVariant(invitation.role)}
                          className="flex items-center gap-1 w-fit"
                        >
                          {getRoleIcon(invitation.role)}
                          {invitation.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {new Date(invitation.invited_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Badge variant={invitation.status === 'pending' ? 'default' : 'destructive'}>
                          {invitation.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};
