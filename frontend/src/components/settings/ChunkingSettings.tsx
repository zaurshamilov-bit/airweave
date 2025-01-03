import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Cpu } from "lucide-react";

export function ChunkingSettings() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          <CardTitle>Chunking Configuration</CardTitle>
        </div>
        <CardDescription>
          Configure how your documents are processed and chunked
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <Label>Chunk Size (tokens)</Label>
          <Slider 
            defaultValue={[512]} 
            max={2048} 
            min={128} 
            step={128}
            className="w-full"
          />
          <div className="text-sm text-muted-foreground">
            Recommended: 512 tokens for optimal context window usage
          </div>
        </div>

        <div className="space-y-2">
          <Label>Chunk Overlap</Label>
          <Slider 
            defaultValue={[50]} 
            max={100} 
            min={0}
            className="w-full"
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Smart Chunking</Label>
            <div className="text-sm text-muted-foreground">
              Use ML to detect natural break points
            </div>
          </div>
          <Switch defaultChecked />
        </div>
      </CardContent>
    </Card>
  );
}