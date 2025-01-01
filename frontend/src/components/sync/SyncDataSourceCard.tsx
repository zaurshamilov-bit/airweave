import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppIconUrl } from "@/lib/utils/icons";
import { Info, ChevronDown, Check } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Connection {
  id: string;
  name: string;
  isSelected?: boolean;
}

interface SyncDataSourceCardProps {
  shortName: string;
  name: string;
  description: string;
  status: "connected" | "disconnected";
  onSelect: () => void;
  connections?: Connection[];
}

export function SyncDataSourceCard({ 
  shortName, 
  name, 
  description, 
  status, 
  onSelect,
  connections = [],
}: SyncDataSourceCardProps) {
  return (
    <Card className="w-full min-h-[240px] flex flex-col justify-between overflow-hidden">
      <CardHeader className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start space-x-3 flex-1 min-w-0">
            <div className="w-8 h-8 shrink-0 flex items-center justify-center">
              <img 
                src={getAppIconUrl(shortName)} 
                alt={`${name} icon`}
                className="w-6 h-6"
              />
            </div>
            <div className="min-w-0 flex-1">
              <CardTitle className="text-lg mb-1 line-clamp-1">{name}</CardTitle>
              <CardDescription className="line-clamp-2">{description}</CardDescription>
            </div>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Info className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Click to learn more about this source</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </CardHeader>
      <CardContent className="p-4 pt-0 flex-grow">
        <p className="text-sm text-muted-foreground line-clamp-3">
          Extract and sync your {name} data to your vector database of choice.
        </p>
      </CardContent>
      <CardFooter className="p-4 pt-0">
        <div className="flex w-full gap-1">
          <Button 
            onClick={onSelect} 
            variant={status === "connected" ? "secondary" : "default"}
            className="flex-1"
          >
            {status === "connected" ? "Choose Source" : "Connect"}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant={status === "connected" ? "secondary" : "default"}
                className="px-2"
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[280px]">
              {connections.length > 0 ? (
                <>
                  {connections.map((connection) => (
                    <DropdownMenuItem key={connection.id} className="cursor-pointer">
                      <div className="flex items-center justify-between w-full">
                        <div className="flex flex-col">
                          <span className="font-medium">{connection.name}</span>
                          <span className="text-xs text-muted-foreground">
                            ID: {connection.id.substring(0, 8)}
                          </span>
                        </div>
                        {connection.isSelected && (
                          <Check className="h-4 w-4 text-primary ml-2" />
                        )}
                      </div>
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                </>
              ) : null}
              <DropdownMenuItem className="cursor-pointer">
                <span className="font-medium text-primary">Add new connection</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardFooter>
    </Card>
  );
}