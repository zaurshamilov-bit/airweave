import { AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface SyncErrorCardProps {
    error: string;
    isDark: boolean;
}

export const SyncErrorCard = ({
    error,
    isDark
}: SyncErrorCardProps) => {
    return (
        <Card className={cn(
            "overflow-hidden border rounded-lg p-0",
            isDark
                ? "border-red-800/10 bg-transparent"
                : "border-gray-200 bg-white"
        )}>
            <CardHeader className="px-3 py-3 pb-0">
                <h3 className={cn(
                    "text-base font-medium flex items-center",
                    isDark ? "text-red-400/80" : "text-red-500/90"
                )}>
                    <AlertCircle className="h-4 w-4 mr-2 stroke-[2.5px]" />
                    Sync Error
                </h3>
            </CardHeader>
            <CardContent className="px-3 py-3">
                <div className={cn(
                    "p-4 rounded-md font-mono text-xs whitespace-pre-wrap overflow-auto max-h-48",
                    isDark
                        ? "bg-gray-800/50 text-gray-200 border border-gray-700"
                        : "bg-gray-50 text-gray-700 border border-gray-200"
                )}>
                    {error}
                </div>
                <p className={cn(
                    "text-sm mt-3 flex items-center",
                    isDark ? "text-gray-400" : "text-gray-500"
                )}>
                    Please fix the error and try running the sync again.
                </p>
            </CardContent>
        </Card>
    );
};
