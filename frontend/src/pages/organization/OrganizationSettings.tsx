import { useState, useEffect } from 'react';
import { useOrganizationStore } from '@/lib/stores/organization-store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Building2, Save, Trash2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

export const OrganizationSettings = () => {
  const { currentOrganization, updateOrganization } = useOrganizationStore();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (currentOrganization) {
      setName(currentOrganization.name);
      setDescription(currentOrganization.description || '');
    }
  }, [currentOrganization]);

  const handleSave = async () => {
    if (!currentOrganization) return;

    try {
      setIsLoading(true);

      // For now, just update the store directly since API isn't ready
      updateOrganization(currentOrganization.id, { name, description });

      // TODO: Uncomment when API is ready
      // const response = await apiClient.put(`/organizations/${currentOrganization.id}`, {
      //   name,
      //   description
      // });
      // if (!response.ok) {
      //   throw new Error(`Failed to update organization: ${response.status}`);
      // }

    } catch (error) {
      console.error('Failed to update organization:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentOrganization) {
    return <div>No organization selected</div>;
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      <div className="flex items-center gap-2 mb-6">
        <Building2 className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Organization Settings</h1>
        <Badge variant="outline">
          {currentOrganization.role}
        </Badge>
      </div>

      <div className="grid gap-6">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
            <CardDescription>
              Update your organization's basic information.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="name">Organization Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter organization name"
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter organization description"
                rows={3}
              />
            </div>

            <Button
              onClick={handleSave}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              {isLoading ? 'Saving...' : 'Save Changes'}
            </Button>
          </CardContent>
        </Card>

        {/* Organization ID */}
        <Card>
          <CardHeader>
            <CardTitle>Organization ID</CardTitle>
            <CardDescription>
              Your organization's unique identifier.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Input
                value={currentOrganization.id}
                readOnly
                className="font-mono text-sm"
              />
              <Button
                variant="outline"
                onClick={() => navigator.clipboard.writeText(currentOrganization.id)}
              >
                Copy
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        {currentOrganization.role === 'owner' && (
          <Card className="border-red-200">
            <CardHeader>
              <CardTitle className="text-red-600">Danger Zone</CardTitle>
              <CardDescription>
                These actions cannot be undone.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="destructive" className="flex items-center gap-2">
                <Trash2 className="h-4 w-4" />
                Delete Organization
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};
