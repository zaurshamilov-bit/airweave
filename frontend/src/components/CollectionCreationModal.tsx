import React, { useEffect } from 'react';
import { Dialog, DialogContent, DialogOverlay, DialogPortal } from '@/components/ui/dialog';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Database, FileText, Link2, CheckCircle, Circle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Import view components (we'll create these next)
import { CollectionFormView } from './creation-views/CollectionFormView';
import { SourceSelectView } from './creation-views/SourceSelectView';
import { SourceConfigView } from './creation-views/SourceConfigView';
import { OAuthRedirectView } from './creation-views/OAuthRedirectView';
import { SuccessView } from './creation-views/SuccessView';

export const CollectionCreationModal: React.FC = () => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const {
    isOpen,
    currentStep,
    closeModal,
    setStep,
    reset,
  } = useCollectionCreationStore();

  // Add ESC key handler for emergency close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

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
        setStep('success');

        // Re-open modal if it was closed
        if (!isOpen) {
          useCollectionCreationStore.getState().openModal();
        }
      } else if (status === 'error') {
        // Handle error
        console.error('OAuth error');
        // Could show error view here
      }

      // Clean up URL
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [searchParams, setStep, isOpen]);

  const handleClose = () => {
    // Immediately set isOpen to false
    useCollectionCreationStore.setState({ isOpen: false });

    // Then call closeModal which will do cleanup
    closeModal();

    // Clear URL params
    const newUrl = window.location.pathname;
    window.history.replaceState({}, '', newUrl);
  };

  const renderCurrentView = () => {
    switch (currentStep) {
      case 'collection-form':
        return <CollectionFormView />;
      case 'source-select':
        return <SourceSelectView />;
      case 'source-config':
        return <SourceConfigView />;
      case 'oauth-redirect':
        return <OAuthRedirectView />;
      case 'success':
        return <SuccessView onComplete={handleClose} />;
      default:
        return null;
    }
  };

  const renderCollectionVisualization = () => {
    const { collectionName, sourceName, connectionId } = useCollectionCreationStore.getState();

    const steps = [
      { id: 'collection', label: 'Collection', icon: Database, completed: !!collectionName },
      { id: 'source', label: 'Source', icon: FileText, completed: !!sourceName },
      { id: 'connect', label: 'Connect', icon: Link2, completed: !!connectionId },
    ];

    return (
      <div className="h-full p-8 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800">
        <div className="h-full flex flex-col justify-center">
          <div className="text-center mb-8">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {collectionName || 'New Collection'}
            </h3>
            {sourceName && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Connecting to {sourceName}
              </p>
            )}
          </div>

          {/* Progress Steps */}
          <div className="space-y-6">
            {steps.map((step, index) => {
              const Icon = step.icon;
              const isActive =
                (currentStep === 'collection-form' && step.id === 'collection') ||
                (currentStep === 'source-select' && step.id === 'source') ||
                (currentStep === 'source-config' && step.id === 'source') ||
                (currentStep === 'oauth-redirect' && step.id === 'connect') ||
                (currentStep === 'success' && step.id === 'connect');

              return (
                <div key={step.id} className="flex items-center gap-4">
                  <div className={cn(
                    "w-12 h-12 rounded-full flex items-center justify-center transition-all",
                    step.completed ? "bg-green-500 text-white" :
                    isActive ? "bg-blue-500 text-white" :
                    "bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500"
                  )}>
                    {step.completed ? (
                      <CheckCircle className="w-6 h-6" />
                    ) : (
                      <Icon className="w-6 h-6" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={cn(
                      "font-medium",
                      step.completed || isActive ?
                        "text-gray-900 dark:text-gray-100" :
                        "text-gray-400 dark:text-gray-500"
                    )}>
                      {step.label}
                    </p>
                    {step.completed && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {step.id === 'collection' && collectionName}
                        {step.id === 'source' && sourceName}
                        {step.id === 'connect' && 'Connected'}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Visual Connection Lines */}
          <div className="mt-12 flex justify-center">
            <div className="relative">
              <div className="w-32 h-32 rounded-full bg-gradient-to-br from-blue-400 to-purple-400 opacity-20 animate-pulse" />
              <div className="absolute inset-4 w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 opacity-40" />
              <div className="absolute inset-8 w-16 h-16 rounded-full bg-white dark:bg-gray-800 flex items-center justify-center">
                <Database className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      // Allow closing the dialog
      if (!open) {
        handleClose();
      }
    }}>
      <DialogPortal>
        <DialogOverlay className="bg-black/50 backdrop-blur-sm" />
        <DialogContent
          className={cn(
            "p-0 rounded-2xl border-0 overflow-hidden shadow-2xl",
            "w-[1200px] max-w-[95vw] h-[700px] max-h-[90vh]",
            isDark ? "bg-gray-900" : "bg-white"
          )}
          onPointerDownOutside={(e) => {
            // Only prevent closing during OAuth redirect step
            if (currentStep === 'oauth-redirect') {
              e.preventDefault();
            }
          }}
        >
          <div className="relative h-full flex">
            {/* Close button */}
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-4 right-4 z-50"
              onClick={handleClose}
            >
              <X className="h-4 w-4" />
            </Button>

            {/* Left side - Main content */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Simple progress indicator */}
              <div className="h-1 bg-gray-200 dark:bg-gray-800">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{
                    width: `${
                      currentStep === 'collection-form' ? 20 :
                      currentStep === 'source-select' ? 40 :
                      currentStep === 'source-config' ? 60 :
                      currentStep === 'oauth-redirect' ? 80 :
                      100
                    }%`
                  }}
                />
              </div>

              {/* View content */}
              <div className="flex-1 overflow-auto">
                {renderCurrentView()}
              </div>
            </div>

            {/* Right side - Collection visualization */}
            <div className="w-[400px] border-l border-gray-200 dark:border-gray-800">
              {renderCollectionVisualization()}
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
};
