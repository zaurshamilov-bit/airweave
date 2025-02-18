import { memo, useState } from "react";
import { EdgeProps, getBezierPath } from "reactflow";
import { PlusCircle } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// Mock transformers - replace with actual transformers later
const TRANSFORMERS = [
  { id: "text-splitter", name: "Text Splitter", description: "Split text into chunks" },
  { id: "summarizer", name: "Summarizer", description: "Generate text summaries" },
  { id: "translator", name: "Translator", description: "Translate text between languages" },
  { id: "classifier", name: "Classifier", description: "Classify text into categories" },
];

export const ButtonEdge = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}: EdgeProps) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const [isOpen, setIsOpen] = useState(false);

  const handleTransformerSelect = (transformerId: string) => {
    // TODO: Implement transformer node creation
    console.log("Selected transformer:", transformerId);
    setIsOpen(false);
  };

  return (
    <>
      <path
        id={id}
        style={style}
        className="react-flow__edge-path stroke-muted-foreground"
        d={edgePath}
        markerEnd={markerEnd}
      />
      <foreignObject
        width={40}
        height={40}
        x={labelX - 20}
        y={labelY - 20}
        className="overflow-visible"
      >
        <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center justify-center w-6 h-6 rounded-full bg-background border border-border hover:border-primary transition-colors">
              <PlusCircle className="w-4 h-4 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="w-64">
            {TRANSFORMERS.map((transformer) => (
              <DropdownMenuItem
                key={transformer.id}
                onClick={() => handleTransformerSelect(transformer.id)}
              >
                <div className="flex flex-col">
                  <span className="font-medium">{transformer.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {transformer.description}
                  </span>
                </div>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </foreignObject>
    </>
  );
});

ButtonEdge.displayName = "ButtonEdge"; 