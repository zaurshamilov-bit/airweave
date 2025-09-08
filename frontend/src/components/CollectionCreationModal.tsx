import React, { useEffect, useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { X } from 'lucide-react';

// Import view components
import { CollectionFormView } from './creation-views/CollectionFormView';
import { SourceSelectView } from './creation-views/SourceSelectView';
import { SourceConfigView } from './creation-views/SourceConfigView';
import { OAuthRedirectView } from './creation-views/OAuthRedirectView';
import { SuccessView } from './creation-views/SuccessView';
import { CollectionVisualization } from './creation-views/CollectionVisualization';

export const CollectionCreationModal: React.FC = () => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [humanReadableId, setHumanReadableId] = useState<string>('');

  const {
    isOpen,
    currentStep,
    flowType,
    collectionName,
    existingCollectionName,
    selectedSource,
    sourceName,
    closeModal,
    setStep,
    reset,
    isAddingToExistingCollection,
  } = useCollectionCreationStore();

  // Generate human-readable ID when collection name changes (only for new collections)
  useEffect(() => {
    // Only generate for new collections, not when adding to existing
    if (!isAddingToExistingCollection()) {
      const generateHumanReadableId = () => {
        // This is a placeholder - you'll provide the exact algorithm later
        const adjectives = ['quick', 'bright', 'cool', 'smart', 'fresh'];
        const nouns = ['fox', 'star', 'wave', 'cloud', 'tree'];
        const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
        const noun = nouns[Math.floor(Math.random() * nouns.length)];
        const num = Math.floor(Math.random() * 100);
        return `${adj}-${noun}-${num}`;
      };

      setHumanReadableId(generateHumanReadableId());
    }
  }, [collectionName, isAddingToExistingCollection]);

  // Handle OAuth callback
  useEffect(() => {
    const isOAuthReturn = searchParams.get('oauth_return') === 'true';
    const status = searchParams.get('status');
    const connectionId = searchParams.get('source_connection_id');

    if (isOAuthReturn) {
      if (status === 'success' || status === 'sync_started') {
        // OAuth successful
        if (connectionId) {
          useCollectionCreationStore.getState().setConnectionId(connectionId);
        }

        // Only update step and re-open if we have valid collection data
        // (this means the user didn't close the modal intentionally)
        const store = useCollectionCreationStore.getState();
        if (store.collectionName || store.existingCollectionId) {
          setStep('success');

          // Re-open modal if it was closed during OAuth
          if (!isOpen) {
            // Just set isOpen without resetting state
            store.openModal('success');
          }
        }
      } else if (status === 'error') {
        // Handle error
        console.error('OAuth error');
      }

      // Clean up URL
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [searchParams, setStep, isOpen]);

  const handleClose = () => {
    // Don't close during OAuth redirect
    if (currentStep === 'oauth-redirect') {
      return;
    }

    // Clear URL params
    const newUrl = window.location.pathname;
    window.history.replaceState({}, '', newUrl);

    // Close the modal immediately - this MUST set isOpen to false
    closeModal();

    // Double-check it's actually closed
    console.log('Modal closing, isOpen should be false:', useCollectionCreationStore.getState().isOpen);

    // Reset state after modal is fully closed (animation complete)
    // This prevents the "stateless" modal issue
    setTimeout(() => {
      reset();
    }, 500); // Increased delay to ensure modal is fully closed
  };

  const renderCurrentView = () => {
    // For add-to-collection flow, skip collection form
    if (isAddingToExistingCollection() && currentStep === 'collection-form') {
      setStep('source-select');
      return null;
    }

    switch (currentStep) {
      case 'collection-form':
        return <CollectionFormView humanReadableId={humanReadableId} />;
      case 'source-select':
        // Source select is rendered differently (full width)
        return null;
      case 'source-config':
        return <SourceConfigView
          humanReadableId={humanReadableId}
          isAddingToExisting={isAddingToExistingCollection()}
        />;
      case 'oauth-redirect':
        return <OAuthRedirectView />;
      case 'success':
        return <SuccessView
          onComplete={handleClose}
          isAddingToExisting={isAddingToExistingCollection()}
        />;
      default:
        return null;
    }
  };

  // Determine if we should show the visualization
  // Don't show visualization when adding to existing collection
  const showVisualization = !isAddingToExistingCollection() &&
                           currentStep !== 'source-select' &&
                           currentStep !== 'oauth-redirect';

  // Determine column widths based on step
  const getColumnWidths = () => {
    // Use much wider form column for source-config (URL sharing needs more space)
    if (currentStep === 'source-config') {
      return { left: 'w-[600px]', right: 'flex-1' };
    }
    return { left: 'w-[420px]', right: 'flex-1' };
  };

  const columnWidths = getColumnWidths();

  // Debug logging
  console.log('Modal render - isOpen:', isOpen, 'currentStep:', currentStep);

  return (
    <DialogPrimitive.Root
      open={isOpen}
      onOpenChange={(open) => {
        console.log('onOpenChange called - open:', open, 'isOpen:', isOpen);
        // Only handle close events, not open events
        if (!open && isOpen) {
          handleClose();
        }
      }}
    >
      <DialogPrimitive.Portal>
        {/* Custom overlay */}
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />

        {/* Custom content without animations */}
        <DialogPrimitive.Content
          className={cn(
            "fixed left-[50%] top-[50%] z-50",
            "translate-x-[-50%] translate-y-[-50%]",
            "w-[1400px] max-w-[95vw] h-[800px] max-h-[95vh]",
            "rounded-xl shadow-2xl border overflow-hidden",
            isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"
          )}
          onPointerDownOutside={(e) => {
            // Prevent closing on outside click during OAuth
            if (currentStep === 'oauth-redirect') {
              e.preventDefault();
            }
          }}
          onEscapeKeyDown={(e) => {
            // Prevent escape key during OAuth
            if (currentStep === 'oauth-redirect') {
              e.preventDefault();
            }
          }}
        >
          {/* Hidden title and description for accessibility */}
          <VisuallyHidden.Root>
            <DialogPrimitive.Title>
              {isAddingToExistingCollection() ? 'Add Source to Collection' : 'Create New Collection'}
            </DialogPrimitive.Title>
            <DialogPrimitive.Description>
              {isAddingToExistingCollection()
                ? 'Add a new data source to your existing collection'
                : 'Create a new collection and connect your data sources'}
            </DialogPrimitive.Description>
          </VisuallyHidden.Root>

          {/* Custom close button */}
          <button
            onClick={handleClose}
            className={cn(
              "absolute top-6 right-6 z-10 p-2 rounded-lg transition-colors",
              isDark
                ? "hover:bg-gray-800 text-gray-400 hover:text-gray-200"
                : "hover:bg-gray-100 text-gray-500 hover:text-gray-700"
            )}
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Two-column layout with dynamic widths */}
          {currentStep === 'source-select' ? (
            // Full width for source select
            <SourceSelectView
              humanReadableId={humanReadableId}
              isAddingToExisting={isAddingToExistingCollection()}
            />
          ) : (
            <div className="flex h-full">
              {/* Left column - Form */}
              <div className={cn(
                "border-r overflow-auto transition-all duration-300",
                columnWidths.left,
                isDark ? "border-gray-800 bg-gray-900" : "border-gray-200 bg-white"
              )}>
                {renderCurrentView()}
              </div>

              {/* Right column - Visualization */}
              {showVisualization && (
                <div className={cn(
                  "overflow-auto transition-all duration-300",
                  columnWidths.right,
                  isDark ? "bg-gray-950" : "bg-gray-50"
                )}>
                  <CollectionVisualization
                    collectionName={isAddingToExistingCollection() ? existingCollectionName || collectionName : collectionName}
                    humanReadableId={humanReadableId}
                    selectedSource={selectedSource}
                    sourceName={sourceName}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};
