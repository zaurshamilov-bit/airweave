import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface ReasoningIndicatorProps {
  isVisible: boolean;
}

const reasoningSteps = [
  "Rephrasing question for optimal search query.",
  "Found 10 relevant items.",
  "3 items seem very interesting. I will look into it a bit further...",
  "I think I found what the user is asking for. Let's double-check by going through neighboring nodes",
  "Analyzing the most relevant information.",
  "Preparing a comprehensive response."
];

export function ReasoningIndicator({ isVisible }: ReasoningIndicatorProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [displayedStep, setDisplayedStep] = useState(reasoningSteps[0]);

  useEffect(() => {
    if (!isVisible) return;

    const interval = setInterval(() => {
      setIsTransitioning(true);

      setTimeout(() => {
        const nextIndex = (currentStepIndex + 1) % reasoningSteps.length;
        setCurrentStepIndex(nextIndex);
        setDisplayedStep(reasoningSteps[nextIndex]);
        setIsTransitioning(false);
      }, 300); // This matches the transition duration

    }, 2000); // Change thoughts every 2 seconds

    return () => clearInterval(interval);
  }, [isVisible, currentStepIndex]);

  if (!isVisible) return null;

  return (
    <div className="flex justify-start mb-4">
      <div
        className={cn(
          "border border-border/30 rounded-lg p-4 max-w-[80%] bg-transparent"
        )}
      >
        <div className="flex items-center space-x-2">
          <Loader2 className="h-4 w-4 text-foreground/70 animate-spin" />
          <div
            className={cn(
              "text-sm text-foreground/90 transition-opacity duration-300 ease-in-out animate-pulse",
              isTransitioning ? "opacity-0" : "opacity-100"
            )}
          >
            {displayedStep}
          </div>
        </div>
      </div>
    </div>
  );
}
