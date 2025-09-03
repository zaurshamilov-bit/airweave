import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { apiClient } from '@/lib/api';
import { ArrowLeft, Search, Loader2, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

interface Source {
  short_name: string;
  name: string;
  description: string;
  auth_type: string;
  icon_url?: string;
  labels?: string[];
}

export const SourceSelectView: React.FC = () => {
  const {
    selectedSource,
    selectSource,
    setStep,
    closeModal
  } = useCollectionCreationStore();

  const [sources, setSources] = useState<Source[]>([]);
  const [filteredSources, setFilteredSources] = useState<Source[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSources();
  }, []);

  useEffect(() => {
    filterSources();
  }, [searchQuery, selectedCategory, sources]);

  const loadSources = async () => {
    try {
      const response = await apiClient.get('/sources');
      if (response.ok) {
        const data = await response.json();
        setSources(data);
        setFilteredSources(data);
      }
    } catch (error) {
      console.error('Error loading sources:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filterSources = () => {
    let filtered = [...sources];

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(s =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.short_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.description?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Filter by category
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(s =>
        s.labels?.includes(selectedCategory)
      );
    }

    setFilteredSources(filtered);
  };

  // Extract unique categories from sources
  const categories = ['all', ...Array.from(new Set(sources.flatMap(s => s.labels || [])))];

  const handleSelectSource = (source: Source) => {
    selectSource(source.short_name, source.name);

    // Determine auth mode based on auth_type
    const store = useCollectionCreationStore.getState();
    if (source.auth_type?.startsWith('oauth2')) {
      store.setAuthMode('oauth2');
    } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
      store.setAuthMode('direct_auth');
    }

    setStep('source-config');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setStep('collection-form')}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-2xl font-semibold">Select a Source</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Choose where to sync data from
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="p-6 pb-4 space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Category filters */}
        {categories.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {categories.map((cat) => (
              <Button
                key={cat}
                variant={selectedCategory === cat ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedCategory(cat)}
                className="capitalize"
              >
                {cat === 'all' ? 'All Sources' : cat.replace('_', ' ')}
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Source Grid */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : filteredSources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="text-gray-400 mb-2">
              {searchQuery || selectedCategory !== 'all' ? 'No sources found' : 'No sources available'}
            </div>
            {(searchQuery || selectedCategory !== 'all') && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCategory('all');
                }}
              >
                Clear filters
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {filteredSources.map((source) => (
              <button
                key={source.short_name}
                onClick={() => handleSelectSource(source)}
                className={cn(
                  "group relative p-5 rounded-xl border-2 text-left transition-all",
                  "hover:border-blue-500 hover:shadow-lg hover:scale-[1.02]",
                  selectedSource === source.short_name
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950 shadow-md"
                    : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                )}
              >
                {/* Selected indicator */}
                {selectedSource === source.short_name && (
                  <div className="absolute top-3 right-3">
                    <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                      <Check className="w-4 h-4 text-white" />
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <div className="font-semibold text-base">{source.name}</div>

                  {source.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                      {source.description}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1 mt-3">
                    {source.auth_type && (
                      <Badge variant="secondary" className="text-xs">
                        {source.auth_type.replace('_', ' ')}
                      </Badge>
                    )}
                    {source.labels?.map((label) => (
                      <Badge key={label} variant="outline" className="text-xs">
                        {label.replace('_', ' ')}
                      </Badge>
                    ))}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="p-6 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-3">
          <Button variant="outline" onClick={closeModal} className="flex-1">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
};
