import { useState } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, Check, ArrowLeft, ArrowRight } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdvancedVectorSettings } from "./AdvancedVectorSettings";
import { BasicSettingsForm } from "./BasicSettingsForm";

interface AddDestinationWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete: (dbId: string) => void;
}

interface DestinationConfig {
  name: string;
  url?: string;
  apiKey?: string;
  shortName: string;
}

const vectorDatabases = [
  {
    id: "airweave-weaviate",
    title: "Native Weaviate",
    description: "Connect to local Weaviate instance",
    shortName: "airweave",
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

export const AddDestinationWizard = ({ open, onOpenChange, onComplete }: AddDestinationWizardProps) => {
  const [step, setStep] = useState(1);
  const [selectedDB, setSelectedDB] = useState<string | null>(null);
  const [config, setConfig] = useState<DestinationConfig>({ name: "", shortName: "" });
  const [testing, setTesting] = useState(false);
  const [activeTab, setActiveTab] = useState("basic");

  const totalSteps = 3;
  const selectedDbInfo = vectorDatabases.find(db => db.id === selectedDB);

  const handleDBSelect = (dbId: string) => {
    const db = vectorDatabases.find(db => db.id === dbId);
    if (db) {
      if (db.skipCredentials) {
        onComplete(dbId);
        onOpenChange(false);
      } else {
        setSelectedDB(dbId);
        setConfig({ name: "", shortName: db.shortName });
        setStep(2);
      }
    }
  };

  const handleBack = () => {
    if (step === 2) {
      setStep(1);
      setActiveTab("basic");
    } else if (step === 3) {
      setStep(2);
    }
  };

  const validateBasicSettings = () => {
    if (!config.name.trim()) {
      toast.error("Please enter a name for your database");
      return false;
    }
    
    if (selectedDbInfo?.requiresUrl && !config.url?.trim()) {
      toast.error("Please enter the database URL");
      return false;
    }

    if (!config.apiKey?.trim()) {
      toast.error("Please enter your API key");
      return false;
    }

    return true;
  };

  const handleNext = () => {
    if (step === 2) {
      // Always validate basic settings before proceeding
      if (!validateBasicSettings()) {
        setActiveTab("basic");
        return;
      }
      setStep(3);
    }
  };

  const handleTabChange = (value: string) => {
    if (value === "advanced" && !validateBasicSettings()) {
      return;
    }
    setActiveTab(value);
  };

  const handleTest = async () => {
    setTesting(true);
    
    try {
      // Simulate API test
      await new Promise(resolve => setTimeout(resolve, 1500));
      toast.success("Connection test successful! Your database is now connected.");
      onComplete(selectedDB!);
      onOpenChange(false);
    } catch (error) {
      toast.error("Failed to connect to the database. Please check your settings.");
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <div className="mb-8">
          <div className="relative">
            <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-primary-100">
              <div
                style={{ width: `${(step / totalSteps) * 100}%` }}
                className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-primary transition-all duration-500"
              />
            </div>
            <div className="flex justify-between">
              {Array.from({ length: totalSteps }).map((_, index) => (
                <div
                  key={index}
                  className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors duration-200 ${
                    step > index + 1
                      ? "bg-primary border-primary text-white"
                      : step === index + 1
                      ? "border-primary text-primary"
                      : "border-gray-300 text-gray-300"
                  }`}
                >
                  {step > index + 1 ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {step === 1 && (
            <div className="space-y-4 animate-in slide-in-from-right">
              <div className="space-y-2">
                <h2 className="text-2xl font-bold">Choose Vector Database</h2>
                <p className="text-muted-foreground">
                  Select the vector database you want to connect to.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {vectorDatabases.map((db) => (
                  <Card 
                    key={db.id} 
                    className={`relative overflow-hidden cursor-pointer transition-all hover:shadow-lg ${
                      selectedDB === db.id ? 'ring-2 ring-primary' : ''
                    }`}
                    onClick={() => handleDBSelect(db.id)}
                  >
                    <CardHeader>
                      <div className="flex items-center space-x-4">
                        <div>
                          <CardTitle>{db.title}</CardTitle>
                          <CardDescription>{db.description}</CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-in slide-in-from-right">
              <div className="space-y-2">
                <h2 className="text-2xl font-bold">Configure Connection</h2>
                <p className="text-muted-foreground">
                  Enter the details for your vector database connection.
                </p>
              </div>

              <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="basic">Basic Settings</TabsTrigger>
                  <TabsTrigger value="advanced">Advanced Settings</TabsTrigger>
                </TabsList>

                <TabsContent value="basic">
                  <BasicSettingsForm
                    name={config.name}
                    url={config.url}
                    apiKey={config.apiKey}
                    requiresUrl={selectedDbInfo?.requiresUrl}
                    onConfigChange={(newConfig) => setConfig({ ...config, ...newConfig })}
                  />
                </TabsContent>

                <TabsContent value="advanced">
                  <AdvancedVectorSettings />
                </TabsContent>
              </Tabs>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-in slide-in-from-right">
              <div className="space-y-2">
                <h2 className="text-2xl font-bold">Finalize Setup</h2>
                <p className="text-muted-foreground">
                  Review your configuration and test the connection.
                </p>
              </div>
              <div className="space-y-4 rounded-lg border p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Name</p>
                    <p className="font-medium">{config.name}</p>
                  </div>
                  {config.url && (
                    <div>
                      <p className="text-sm text-muted-foreground">URL</p>
                      <p className="font-medium">{config.url}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-between mt-8">
          {step > 1 && (
            <Button variant="outline" onClick={handleBack}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
          )}
          {step < 3 ? (
            <Button className="ml-auto" onClick={handleNext}>
              Next <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button
              className="ml-auto"
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing Connection
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Complete Setup
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
