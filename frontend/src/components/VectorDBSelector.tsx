import { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { getDestinationIconUrl } from "@/lib/utils/icons";


const vectorDatabases = [
  {
    id: "native-weaviate",
    title: "Native Weaviate",
    description: "Connect to local Weaviate instance",
    shortName: "weaviate",
    skipCredentials: true,
  },
  {
    id: "pinecone",
    title: "Pinecone",
    description: "Serverless vector database with automatic scaling",
    shortName: "pinecone",
  },
  {
    id: "weaviate",
    title: "Weaviate Cloud",
    description: "Open-source vector search engine",
    shortName: "weaviate",
    requiresUrl: true,
  },
  {
    id: "milvus",
    title: "Milvus",
    description: "Open-source vector database for scalable similarity search",
    shortName: "milvus",
  },
];

interface VectorDBSelectorProps {
  onComplete: (dbId: string) => void;
}

export const VectorDBSelector = ({ onComplete }: VectorDBSelectorProps) => {
  const [selectedDB, setSelectedDB] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [url, setUrl] = useState("");
  const [testing, setTesting] = useState(false);

  const selectedDbInfo = vectorDatabases.find(db => db.id === selectedDB);

  const handleSelect = (dbId: string) => {
    const db = vectorDatabases.find(db => db.id === dbId);
    if (db) {
      if (db.skipCredentials) {
        onComplete(dbId);
      } else {
        setSelectedDB(dbId);
        setShowApiKey(true);
      }
    }
  };

  const handleConnect = async () => {
    if (!apiKey) {
      toast.error("Please enter an API key");
      return;
    }

    if (selectedDbInfo?.requiresUrl && !url) {
      toast.error("Please enter the database URL");
      return;
    }

    setTesting(true);
    // Simulate API test
    await new Promise(resolve => setTimeout(resolve, 1500));
    setTesting(false);
    
    toast.success("Vector database connected successfully");
    onComplete(selectedDB!);
  };

  if (!showApiKey) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {vectorDatabases.map((db) => (
          <Card 
            key={db.id} 
            className={`relative overflow-hidden cursor-pointer transition-all hover:shadow-lg ${
              selectedDB === db.id ? 'ring-2 ring-primary' : ''
            }`}
            onClick={() => handleSelect(db.id)}
          >
            <CardHeader>
              <div className="flex items-center space-x-4">
                <img 
                  src={getDestinationIconUrl(db.shortName)} 
                  alt={`${db.title} icon`}
                  className="w-8 h-8"
                />
                <div>
                  <CardTitle>{db.title}</CardTitle>
                  <CardDescription>{db.description}</CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        ))}


      </div>
    );
  }

  return (
    <>
      <div className="max-w-md mx-auto">
        <Card>
          <CardHeader>
            <div className="flex items-center space-x-4">
              <img 
                src={getDestinationIconUrl(selectedDbInfo?.shortName ?? '')} 
                alt={`${selectedDbInfo?.title} icon`}
                className="w-8 h-8"
              />
              <div>
                <CardTitle>{selectedDbInfo?.title}</CardTitle>
                <CardDescription>Configure your connection</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedDbInfo?.requiresUrl && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Database URL</label>
                <Input
                  type="url"
                  placeholder="https://your-instance.weaviate.network"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium">API Key</label>
              <Input
                type="password"
                placeholder={`Enter ${selectedDbInfo?.title} API Key`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="outline" onClick={() => setShowApiKey(false)}>
              Back
            </Button>
            <Button onClick={handleConnect} disabled={testing}>
              {testing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing Connection
                </>
              ) : (
                'Connect'
              )}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </>
  );
};