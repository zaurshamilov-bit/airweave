import React, { CSSProperties } from "react";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";

interface GradientBackgroundProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  intensity?: "light" | "medium" | "strong";
  withNoise?: boolean;
}

/**
 * A component that provides a consistent gradient background from dark to light
 * with proper transparency for child components to blend with.
 */
export function GradientBackground({
  children,
  className,
  withNoise = true,
  ...props
}: GradientBackgroundProps) {
  const { resolvedTheme } = useTheme();

  // Determine gradient intensity based on the prop
  const getGradientClass = () => {
    if (resolvedTheme === 'dark') {
      return "from-black via-black to-background-alpha-20";
    } else {
      return "from-background-alpha-60 via-background-alpha-40 to-background-white";
    }
  };

  const gradientClass = `bg-gradient-to-b ${getGradientClass()}`;

  // CSS for the noise texture overlay
  const noiseStyle: CSSProperties = withNoise ? {
    position: 'relative',
  } : {};

  const noiseAfterStyle: CSSProperties = withNoise ? {
    content: '""',
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    opacity: resolvedTheme === 'dark' ? 0.05 : 0.03,
    backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
    pointerEvents: 'none',
    zIndex: 0,
  } : {};

  return (
    <div
      className={cn(gradientClass, className)}
      style={noiseStyle}
      {...props}
    >
      {withNoise && <div style={noiseAfterStyle} aria-hidden="true" />}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>
    </div>
  );
}

/**
 * A component that provides a semi-transparent card with backdrop blur
 * to be used on top of the gradient background.
 */
export function GradientCard({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const { resolvedTheme } = useTheme();

  const bgClass = resolvedTheme === 'dark'
    ? "bg-background-alpha-40"
    : "bg-background-alpha-10";

  return (
    <div
      className={cn(
        `${bgClass} backdrop-blur-xs`,
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
