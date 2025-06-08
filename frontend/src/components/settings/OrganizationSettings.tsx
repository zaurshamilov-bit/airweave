import { useState, useEffect } from "react";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Save } from 'lucide-react';
import { apiClient } from "@/lib/api";
import { toast } from 'sonner';

interface Organization {
  id: string;
  name: string;
  description?: string;
  role: string;
}

interface OrganizationSettingsProps {
  currentOrganization: Organization;
  onOrganizationUpdate: (id: string, updates: Partial<Organization>) => void;
}

export const OrganizationSettings = ({
  currentOrganization,
  onOrganizationUpdate
}: OrganizationSettingsProps) => {
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

      const response = await apiClient.put(`/organizations/${currentOrganization.id}`, undefined, {
        name,
        description
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update organization: ${response.status}`);
      }

      const updatedOrganization = await response.json();

      onOrganizationUpdate(currentOrganization.id, {
        name: updatedOrganization.name,
        description: updatedOrganization.description
      });

      toast.success('Organization updated successfully');

      setTimeout(() => {
        window.location.reload();
      }, 1000);

    } catch (error) {
      console.error('Failed to update organization:', error);
      toast.error('Failed to update organization');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteOrganization = async () => {
    if (!currentOrganization) return;

    const confirmed = window.confirm('Are you sure you want to delete this organization? This action cannot be undone.');
    if (!confirmed) return;

    try {
      setIsLoading(true);

      const response = await apiClient.delete(`/organizations/${currentOrganization.id}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to delete organization: ${response.status}`);
      }

      toast.success('Organization deleted successfully');
      window.location.href = '/dashboard';

    } catch (error) {
      console.error('Failed to delete organization:', error);
      toast.error('Failed to delete organization');
    } finally {
      setIsLoading(false);
    }
  };

  const canEdit = ['owner', 'admin'].includes(currentOrganization.role);
  const canDelete = currentOrganization.role === 'owner';

  return (
    <div className="space-y-8">
      {/* Basic Information */}
      <div className="space-y-6 max-w-lg">
        <div>
          <Label htmlFor="name" className="text-sm font-medium text-foreground mb-1">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter organization name"
            disabled={!canEdit}
            className="h-9 mt-1 border-border focus:outline-none focus:ring-0 focus:ring-offset-0 focus:shadow-none focus:border-border"
          />
          {!canEdit && (
            <p className="text-xs text-muted-foreground mt-1">
              Only owners and admins can edit
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter organization description (optional)"
            rows={3}
            disabled={!canEdit}
            className="resize-none border-border focus:outline-none focus:ring-0 focus:ring-offset-0 focus:shadow-none focus:border-border placeholder:text-muted-foreground/60 mt-1"
          />
        </div>

        {canEdit && (
          <div className="flex justify-end">
            <Button
              onClick={handleSave}
              disabled={isLoading}
              className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white h-8 px-3.5 text-sm"
            >
              {isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              {isLoading ? 'Saving...' : 'Save changes'}
            </Button>
          </div>
        )}
      </div>

      {/* Danger Zone */}
      {canDelete && (
        <div className="pt-6 border-t border-border max-w-lg">
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium text-foreground">Delete organization</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Permanently delete this organization and all data
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteOrganization}
              disabled={isLoading}
              className="h-8 px-4 text-sm"
            >
              {isLoading ? 'Deleting...' : 'Delete organization'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
