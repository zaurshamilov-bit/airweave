import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

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
          "bg-muted/80 border border-border/70 rounded-lg p-4 max-w-[80%] relative",
          "before:content-[''] before:absolute before:left-[-6px] before:top-[calc(50%-6px)] before:w-3 before:h-3 before:rotate-45 before:bg-muted/80 before:border-l before:border-b before:border-border/70"
        )}
      >
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1">
            <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-pulse"></div>
            <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-pulse delay-150"></div>
            <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-pulse delay-300"></div>
          </div>
          <div
            className={cn(
              "text-sm text-foreground/90 transition-opacity duration-300 ease-in-out",
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
