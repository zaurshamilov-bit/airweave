import React, { useState, useEffect } from 'react';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { HelpCircle } from 'lucide-react';

interface CollectionFormViewProps {
  humanReadableId: string;
}

export const CollectionFormView: React.FC<CollectionFormViewProps> = ({ humanReadableId }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

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

  // Update store when name changes
  useEffect(() => {
    setCollectionData(name);
  }, [name, setCollectionData]);

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
    <div className="h-full flex flex-col">
      <div className="px-8 py-10 flex-1">
        <div className="space-y-8">
          {/* Header */}
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Create Collection
            </h2>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Collections group your data sources for unified search
            </p>
          </div>

          {/* Form */}
          <div className="space-y-6">
            <div>
              <label
                htmlFor="collection-name"
                className={cn(
                  "block text-sm font-medium mb-2",
                  isDark ? "text-gray-200" : "text-gray-700"
                )}
              >
                Name
              </label>
              <input
                id="collection-name"
                type="text"
                placeholder="Engineering documentation"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !isCreating && handleCreate()}
                autoFocus
                className={cn(
                  "w-full px-4 py-2.5 rounded-lg text-sm",
                  "border transition-colors",
                  "focus:outline-none focus:border-gray-400 dark:focus:border-gray-600",
                  isDark
                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                )}
              />
            </div>

            {/* Help text */}
            <div className="flex items-start gap-2">
              <HelpCircle className={cn(
                "h-4 w-4 mt-0.5 flex-shrink-0",
                isDark ? "text-blue-400" : "text-blue-600"
              )} />
              <div className="text-sm">
                <button
                  type="button"
                  className={cn(
                    "font-medium hover:underline",
                    isDark ? "text-blue-400" : "text-blue-600"
                  )}
                  onClick={() => {
                    // Could open a tooltip or modal explaining collections
                  }}
                >
                  What is a collection?
                </button>
                <p className={cn(
                  "mt-1",
                  isDark ? "text-gray-400" : "text-gray-500"
                )}>
                  A collection is a searchable group of connected data sources.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom action */}
      <div className={cn(
        "px-8 py-6 border-t",
        isDark ? "border-gray-800" : "border-gray-200"
      )}>
        <button
          onClick={handleCreate}
          disabled={!name.trim() || isCreating}
          className={cn(
            "w-full py-2 px-4 rounded-lg text-sm font-medium",
            "transition-all",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "bg-blue-600 hover:bg-blue-700 text-white"
          )}
        >
          {isCreating ? 'Creating...' : 'Next'}
        </button>
      </div>
    </div>
  );
};
