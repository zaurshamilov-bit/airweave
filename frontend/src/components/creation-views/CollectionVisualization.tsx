import React from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { getAppIconUrl } from '@/lib/utils/icons';

interface CollectionVisualizationProps {
  collectionName: string;
  humanReadableId: string;
  selectedSource?: string;
  sourceName?: string;
  currentStep: string;
}

export const CollectionVisualization: React.FC<CollectionVisualizationProps> = ({
  collectionName,
  humanReadableId,
  selectedSource,
  sourceName,
  currentStep,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Get source icon using the proper utility function
  const getSourceIcon = () => {
    if (!selectedSource) {
      // Abstract shape when no source selected
      return (
        <div className="w-full h-full flex items-center justify-center">
          <div className={cn(
            "w-24 h-24 rounded-3xl flex items-center justify-center",
            "bg-gradient-to-br from-red-500 to-red-600"
          )}>
            <div className="w-12 h-12 bg-white/20 rounded-full" />
          </div>
        </div>
      );
    }

    // Use the proper utility function to get the icon URL
    const iconUrl = getAppIconUrl(selectedSource, resolvedTheme);

    return (
      <div className="w-full h-full flex items-center justify-center">
        <img
          src={iconUrl}
          alt={sourceName || selectedSource}
          className="w-16 h-16"
        />
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col px-8 py-8">
      <div className="flex-1 flex flex-col justify-center">
        <div className="w-full max-w-lg mx-auto">
          {/* Collection title - with better spacing */}
          <div className="text-center mb-8">
            <h3 className={cn(
              "text-3xl font-light tracking-tight",
              isDark ? "text-white" : "text-gray-900"
            )}>
              {collectionName || 'My Collection'}
            </h3>
          </div>

          {/* Collection container */}
          <div className="relative">
            {/* Header with ID and pseudo-tabs */}
            <div className={cn(
              "rounded-t-xl border border-b px-5 py-3",
              isDark
                ? "bg-gray-800 border-gray-700"
                : "bg-white border-gray-200"
            )}>
              {/* Readable ID */}
              <div className={cn(
                "text-xs font-mono mb-2 opacity-70",
                isDark ? "text-gray-400" : "text-gray-500"
              )}>
                #{humanReadableId}
              </div>

              {/* Pseudo tabs - left aligned, neutral colors */}
              <div className="flex gap-4">
                <button className={cn(
                  "text-xs font-medium transition-colors pb-1",
                  "border-b-2 border-transparent",
                  isDark
                    ? "text-gray-500 hover:text-gray-300"
                    : "text-gray-400 hover:text-gray-600"
                )}>
                  search
                </button>
                <button className={cn(
                  "text-xs font-medium transition-colors pb-1",
                  "border-b-2",
                  isDark
                    ? "text-gray-300 border-gray-500"
                    : "text-gray-700 border-gray-400"
                )}>
                  source connections
                </button>
              </div>
            </div>

            {/* Quadrant visualization - smaller for better proportions */}
            <div className={cn(
              "rounded-b-xl border border-t-0 p-5",
              isDark
                ? "bg-gray-800 border-gray-700"
                : "bg-white border-gray-200"
            )}>
              <div className={cn(
                "grid grid-cols-2 gap-0.5 rounded-lg overflow-hidden",
                isDark ? "bg-gray-900" : "bg-gray-100"
              )}>
                {/* Top left - Selected source icon */}
                <div className={cn(
                  "aspect-square p-5",
                  isDark ? "bg-gray-800" : "bg-white"
                )}>
                  {getSourceIcon()}
                </div>

                {/* Top right - Abstract shape */}
                <div className={cn(
                  "aspect-square p-5",
                  isDark ? "bg-gray-800" : "bg-white"
                )}>
                  <div className="w-full h-full flex items-center justify-center">
                    <div className={cn(
                      "w-24 h-24 rounded-full",
                      isDark ? "bg-gray-700" : "bg-gray-300"
                    )} />
                  </div>
                </div>

                {/* Bottom left - Abstract shape */}
                <div className={cn(
                  "aspect-square p-5",
                  isDark ? "bg-gray-800" : "bg-white"
                )}>
                  <div className="w-full h-full flex items-center justify-center">
                    <div className={cn(
                      "w-24 h-24",
                      isDark ? "bg-gray-700" : "bg-gray-300"
                    )} />
                  </div>
                </div>

                {/* Bottom right - Abstract shape */}
                <div className={cn(
                  "aspect-square p-5",
                  isDark ? "bg-gray-800" : "bg-white"
                )}>
                  <div className="w-full h-full flex items-center justify-center">
                    <div
                      className="w-0 h-0 border-l-[48px] border-l-transparent border-r-[48px] border-r-transparent border-b-[84px]"
                      style={{
                        borderBottomColor: isDark ? 'rgb(107 114 128)' : 'rgb(209 213 219)'
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom message - with better spacing */}
          <div className="text-center mt-8">
            <p className={cn(
              "text-sm opacity-75",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              You can add more sources to this collection later.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
