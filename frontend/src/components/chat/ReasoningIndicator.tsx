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

function PulsingText({ text, isTransitioning }: { text: string; isTransitioning: boolean }) {
  return (
    <div className={cn(
      "text-sm transition-opacity duration-300 ease-in-out flex flex-wrap",
      isTransitioning ? "opacity-0" : "opacity-100"
    )}>
      {text.split('').map((char, index) => (
        <span
          key={index}
          style={{
            animationDelay: `${index * 50}ms`,
            opacity: Math.max(0.2, Math.min(1, index === 0 ? 0.2 : 0.2 + (index / (text.length)) * 0.8)),
            display: 'inline-block',
            width: char === ' ' ? '0.25em' : 'auto',
            transition: 'opacity 0.5s ease-in-out',
            animation: 'pulse 2s infinite',
          }}
        >
          {char === ' ' ? '\u00A0' : char}
        </span>
      ))}
    </div>
  );
}

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
    <div className="flex justify-start mb-2">
      <div
        className="bg-none border border-border/70 rounded-lg p-4 max-w-[80%]"
      >
        <div className="flex items-center space-x-2">
          <Loader2 className="h-4 w-4 animate-spin text-foreground/60" />
          <PulsingText text={displayedStep} isTransitioning={isTransitioning} />
        </div>
      </div>
    </div>
  );
}
