import React, { useState, ReactNode, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import {
    Dialog,
    DialogContent,
    DialogPortal,
    DialogOverlay,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import { AnimatePresence, motion } from "framer-motion";

// Custom DialogContent without animations
const DialogContentNoAnimation = React.forwardRef<
    React.ElementRef<typeof DialogPrimitive.Content>,
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
    <DialogPrimitive.Content
        ref={ref}
        className={cn(
            "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg sm:rounded-lg",
            className
        )}
        {...props}
    >
        {children}
    </DialogPrimitive.Content>
));
DialogContentNoAnimation.displayName = "DialogContentNoAnimation";

// Custom DialogOverlay without animations
const DialogOverlayNoAnimation = React.forwardRef<
    React.ElementRef<typeof DialogPrimitive.Overlay>,
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Overlay
        ref={ref}
        className={cn(
            "fixed inset-0 z-50 bg-black/75",
            className
        )}
        {...props}
    />
));
DialogOverlayNoAnimation.displayName = "DialogOverlayNoAnimation";

// View interface for all dialog views
export interface DialogViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    viewData?: any;
}

export interface FlowDialogProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    initialView: string;
    initialData?: any;
    views: Record<string, React.ComponentType<DialogViewProps>>;
    onComplete?: (data?: any) => void;
    onNext?: (data?: any) => any;
    width?: string;
    height?: string;
    disableAnimations?: boolean;
}

export const FlowDialog: React.FC<FlowDialogProps> = ({
    isOpen,
    onOpenChange,
    initialView,
    initialData = {},
    views,
    onComplete,
    onNext,
    width = "800px",
    height = "1000px",
    disableAnimations = false,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // State for the current view and transition
    const [currentView, setCurrentView] = useState(initialView);
    const [viewHistory, setViewHistory] = useState<string[]>([initialView]);
    const [viewData, setViewData] = useState<Record<string, any>>({ [initialView]: initialData });
    const [direction, setDirection] = useState<"left" | "right">("right");

    // Reset state when dialog opens
    useEffect(() => {
        if (isOpen) {
            setCurrentView(initialView);
            setViewHistory([initialView]);
            setViewData({ [initialView]: initialData });
        }
    }, [isOpen, initialView, initialData]);

    // Get the current view component
    const CurrentViewComponent = views[currentView];

    if (!CurrentViewComponent) {
        console.error(`View "${currentView}" not found in views map`);
        return null;
    }

    // Handler for next view transition
    const handleNext = (nextView: string, data?: any) => {
        setDirection("right");
        setViewHistory(prev => [...prev, nextView]);
        setViewData(prev => ({ ...prev, [nextView]: data }));
        setCurrentView(nextView);
    };

    // Handler for back navigation
    const handleBack = () => {
        if (viewHistory.length <= 1) return;

        setDirection("left");
        const newHistory = [...viewHistory];
        newHistory.pop();
        const prevView = newHistory[newHistory.length - 1];

        setViewHistory(newHistory);
        setCurrentView(prevView);
    };

    // Handler for dialog completion
    const handleComplete = (data?: any) => {
        if (onComplete) {
            onComplete(data);
        }
        onOpenChange(false);
    };

    // Handler for dialog cancellation
    const handleCancel = () => {
        onOpenChange(false);
    };

    // Common props for the current view component
    const viewComponentProps = {
        onNext: (data) => {
            // If custom onNext handler is provided, use it
            if (onNext) {
                const result = onNext(data);
                // If result is null, don't proceed with default behavior
                if (result === null) return;
                // Otherwise use the possibly modified data
                data = result;
            }

            if (typeof data === "string") {
                // If data is a string, treat it as the next view name
                handleNext(data);
            } else if (data && typeof data === "object" && data.view) {
                // If data has a view property, use it as next view with optional data
                handleNext(data.view, data.data);
            }
        },
        onBack: viewHistory.length > 1 ? handleBack : undefined,
        onCancel: handleCancel,
        onComplete: handleComplete,
        viewData: viewData[currentView]
    };

    // Common styles for dialog content
    const contentStyles = {
        width,
        height,
        maxWidth: "95vw",
        maxHeight: "95vh"
    };

    if (disableAnimations) {
        // Render without any animations
        return (
            <Dialog open={isOpen} onOpenChange={onOpenChange}>
                <DialogPortal>
                    <DialogOverlayNoAnimation className="bg-black/75" />
                    <DialogContentNoAnimation
                        className={cn(
                            "p-0 rounded-xl border overflow-hidden",
                            isDark ? "bg-background border-gray-800" : "bg-background border-gray-200"
                        )}
                        style={contentStyles}
                    >
                        <div className="h-full w-full overflow-hidden">
                            <CurrentViewComponent {...viewComponentProps} />
                        </div>
                    </DialogContentNoAnimation>
                </DialogPortal>
            </Dialog>
        );
    }

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogPortal>
                <DialogOverlay className="bg-black/75" />
                <DialogContent
                    className={cn(
                        "p-0 rounded-xl border overflow-hidden",
                        isDark ? "bg-background border-gray-800" : "bg-background border-gray-200"
                    )}
                    style={contentStyles}
                >
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.div
                            key={currentView}
                            initial={{ opacity: 0, x: direction === "right" ? 20 : -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: direction === "right" ? -20 : 20 }}
                            transition={{ duration: 0.2 }}
                            className="h-full w-full overflow-hidden"
                        >
                            <CurrentViewComponent {...viewComponentProps} />
                        </motion.div>
                    </AnimatePresence>
                </DialogContent>
            </DialogPortal>
        </Dialog>
    );
};

export default FlowDialog;
