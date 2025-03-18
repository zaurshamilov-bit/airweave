import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface ReasoningIndicatorProps {
  isVisible: boolean;
}

// Define the phases of reasoning
const phases = {
  initial: ["Thinking..."],
  rephrasing: ["Rephrasing question to format internal query..."],
  processing: [
    "Found {n} matching entities in vector database with similarity above threshold.",
    "Retrieved {n} related nodes from knowledge graph.",
    "Exploring {n} connections between entities in the graph.",
    "Analyzing {n} most relevant text chunks for context.",
    "Traversing {n} levels deep in the knowledge graph.",
    "Merging information from {n} different data sources.",
    "Identified {n} key insights from retrieved documents.",
    "Extracting structured data from {n} relevant passages.",
    "Comparing similarity between {n} vector embeddings.",
    "Resolving {n} entity references across documents."
  ],
  final: ["Writing readable message back to user.."]
};

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
  const [currentPhase, setCurrentPhase] = useState<'initial' | 'rephrasing' | 'processing' | 'final'>('initial');
  const [currentMessage, setCurrentMessage] = useState(phases.initial[0]);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [processingIndex, setProcessingIndex] = useState(0);

  useEffect(() => {
    if (!isVisible) return;

    // Handle phase transitions
    const phaseTimeline = async () => {
      // Start with "Thinking..."
      setCurrentPhase('initial');
      setCurrentMessage(phases.initial[0]);
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Move to "Rephrasing question"
      setIsTransitioning(true);
      await new Promise(resolve => setTimeout(resolve, 300));
      setCurrentPhase('rephrasing');
      setCurrentMessage(phases.rephrasing[0]);
      setIsTransitioning(false);
      await new Promise(resolve => setTimeout(resolve, 3000));

      // Show 3-7 random processing messages
      setCurrentPhase('processing');
      const numMessages = Math.floor(Math.random() * 5) + 3; // 3 to 7 messages

      for (let i = 0; i < numMessages; i++) {
        setIsTransitioning(true);
        await new Promise(resolve => setTimeout(resolve, 300));

        // Select random message and replace {n} with random number 2-7
        const randomIndex = Math.floor(Math.random() * phases.processing.length);
        const randomNumber = Math.floor(Math.random() * 6) + 2; // 2 to 7
        const message = phases.processing[randomIndex].replace('{n}', randomNumber.toString());

        setProcessingIndex(randomIndex);
        setCurrentMessage(message);
        setIsTransitioning(false);

        await new Promise(resolve => setTimeout(resolve, 2000));
      }

      // Finish with "Writing readable message back to user.."
      setIsTransitioning(true);
      await new Promise(resolve => setTimeout(resolve, 300));
      setCurrentPhase('final');
      setCurrentMessage(phases.final[0]);
      setIsTransitioning(false);
    };

    void phaseTimeline();
  }, [isVisible]);

  if (!isVisible) return null;

  return (
    <div className="flex justify-start mb-2">
      <div
        className="bg-none border border-border/70 rounded-lg p-4 max-w-[80%]"
      >
        <div className="flex items-center space-x-2">
          <Loader2 className="h-4 w-4 animate-spin text-foreground/60" />
          <PulsingText text={currentMessage} isTransitioning={isTransitioning} />
        </div>
      </div>
    </div>
  );
}
