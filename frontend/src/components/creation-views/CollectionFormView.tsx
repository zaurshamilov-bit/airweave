import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { Loader2, Database, ArrowRight } from 'lucide-react';

export const CollectionFormView: React.FC = () => {
  const {
    collectionName,
    selectedSource,
    sourceName,
    setCollectionData,
    setCollectionId,
    setStep
  } = useCollectionCreationStore();

  const [name, setName] = useState(collectionName);
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error('Please enter a collection name');
      return;
    }

    setIsCreating(true);
    try {
      const response = await apiClient.post('/collections', {
        name: name.trim(),
        description: `Collection for ${name.trim()}`,
      });

      if (!response.ok) {
        throw new Error('Failed to create collection');
      }

      const collection = await response.json();

      // Store collection data
      setCollectionData(name.trim());
      setCollectionId(collection.readable_id || collection.id);

      // Move to next step based on whether source is pre-selected
      if (selectedSource) {
        setStep('source-config');
      } else {
        setStep('source-select');
      }

    } catch (error) {
      console.error('Error creating collection:', error);
      toast.error('Failed to create collection');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="p-8">
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold mb-2">Create Collection</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            A collection groups your data sources together for unified search
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="collection-name">Name</Label>
            <Input
              id="collection-name"
              placeholder="e.g., Engineering Documentation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
              className="mt-1"
            />
            <p className="text-xs text-gray-500 mt-1">
              Choose a descriptive name for your collection
            </p>
          </div>
        </div>

        {selectedSource && (
          <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <p className="text-sm text-blue-600 dark:text-blue-400">
              Pre-selected source: <strong>{sourceName}</strong>
            </p>
          </div>
        )}

        <Button
          onClick={handleCreate}
          disabled={!name.trim() || isCreating}
          className="w-full"
        >
          {isCreating ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              Next
              <ArrowRight className="w-4 h-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
};
