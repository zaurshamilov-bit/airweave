import React, { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import { CheckCircle, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import confetti from 'canvas-confetti';

interface SuccessViewProps {
  onComplete: () => void;
}

export const SuccessView: React.FC<SuccessViewProps> = ({ onComplete }) => {
  const navigate = useNavigate();
  const {
    collectionId,
    collectionName,
    sourceName,
    reset
  } = useCollectionCreationStore();

  useEffect(() => {
    // Trigger confetti animation
    confetti({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 }
    });

    // Emit event for collection created
    window.dispatchEvent(new CustomEvent('collection-created'));
  }, []);

  const handleGoToCollection = () => {
    if (collectionId) {
      navigate(`/collections/${collectionId}`);
    }
    reset();
    onComplete();
  };

  const handleClose = () => {
    reset();
    onComplete();
  };

  return (
    <div className="p-8">
      <div className="text-center space-y-6">
        <div className="w-20 h-20 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto">
          <CheckCircle className="w-10 h-10 text-green-600 dark:text-green-400" />
        </div>

        <div>
          <h2 className="text-3xl font-bold mb-2">All Set! 🎉</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Your collection is ready and syncing
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-left space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Collection:</span>
            <span className="font-medium">{collectionName}</span>
          </div>
          {sourceName && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Source:</span>
              <span className="font-medium">{sourceName}</span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Status:</span>
            <span className="text-green-600 dark:text-green-400 font-medium">Active</span>
          </div>
        </div>

        <div className="space-y-3">
          <Button onClick={handleGoToCollection} className="w-full">
            Go to Collection
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>

          <Button
            variant="outline"
            onClick={handleClose}
            className="w-full"
          >
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
