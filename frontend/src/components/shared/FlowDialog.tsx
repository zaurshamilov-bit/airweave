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

/**
 * Props interface for all dialog views
 * Each view should implement this interface to ensure compatible communication
 */
export interface DialogViewProps {
    /** Called to move to the next step or view */
    onNext?: (data?: any) => void;
    /** Called to go back to the previous view */
    onBack?: () => void;
    /** Called to cancel the entire flow */
    onCancel?: () => void;
    /** Called to complete the entire flow (success) */
    onComplete?: (data?: any) => void;
    /** Data specific to this view, passed from previous steps */
    viewData?: Record<string, any>;
}

/**
 * FlowDialog component props
 */
export interface FlowDialogProps {
    /** Controls if the dialog is open */
    isOpen: boolean;
    /** Called when dialog open state changes */
    onOpenChange: (open: boolean) => void;
    /** Name of the initial view to display */
    initialView: string;
    /** Initial data to provide to the first view */
    initialData?: Record<string, any>;
    /** Map of view names to view components */
    views: Record<string, React.ComponentType<DialogViewProps>>;
    /** Called when the entire flow completes */
    onComplete?: (data?: any) => void;
    /** Optional handler to intercept and modify transitions */
    onNext?: (data?: any) => any;
    /** Width of the dialog */
    width?: string;
    /** Height of the dialog */
    height?: string;
}

/**
 * FlowDialog component
 *
 * A container component that manages multiple views within a single dialog.
 * Handles navigation between views, history tracking, and data passing.
 */
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
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // State for managing the flow
    const [currentView, setCurrentView] = useState(initialView);
    const [viewHistory, setViewHistory] = useState<string[]>([initialView]);
    const [viewData, setViewData] = useState<Record<string, Record<string, any>>>({ [initialView]: initialData });
    const [direction, setDirection] = useState<"left" | "right">("right");

    // Reset state when dialog opens
    useEffect(() => {
        if (isOpen) {
            setCurrentView(initialView);
            setViewHistory([initialView]);
            setViewData({ [initialView]: initialData });
            setDirection("right");
        }
    }, [isOpen, initialView, initialData]);

    // Get the current view component
    const CurrentViewComponent = views[currentView];

    // Move the useEffect outside the conditional
    useEffect(() => {
        if (isOpen && !CurrentViewComponent) {
            console.error("Closing dialog due to missing view component");
            onOpenChange(false);
        }
    }, [isOpen, onOpenChange, CurrentViewComponent]);

    // Handle missing view component gracefully
    if (!CurrentViewComponent) {
        console.error(`View "${currentView}" not found in views map. Available views: ${Object.keys(views).join(", ")}`);
        return null;
    }

    /**
     * Handler for next view transition
     * @param nextView The name of the next view to display
     * @param data Optional data to pass to the next view
     */
    const handleNext = (nextView: string, data?: any) => {
        // Validate the next view exists
        if (!views[nextView]) {
            console.error(`Cannot navigate to view "${nextView}" - not found in views map`);
            return;
        }

        setDirection("right");
        setViewHistory(prev => [...prev, nextView]);
        setViewData(prev => ({ ...prev, [nextView]: data }));
        setCurrentView(nextView);
    };

    /**
     * Handler for back navigation
     */
    const handleBack = () => {
        if (viewHistory.length <= 1) return;

        setDirection("left");
        const newHistory = [...viewHistory];
        newHistory.pop();
        const prevView = newHistory[newHistory.length - 1];

        setViewHistory(newHistory);
        setCurrentView(prevView);
    };

    /**
     * Handler for dialog completion
     * @param data Optional result data from the flow
     */
    const handleComplete = (data?: any) => {
        if (onComplete) {
            onComplete(data);
        }
        onOpenChange(false);
    };

    /**
     * Handler for dialog cancellation
     */
    const handleCancel = () => {
        onOpenChange(false);
    };

    // Common props for the current view component
    const viewComponentProps: DialogViewProps = {
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

    // Render the dialog with the current view
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
};

export default FlowDialog;
