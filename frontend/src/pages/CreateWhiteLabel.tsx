import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { WhiteLabelForm } from "@/components/white-label/WhiteLabelForm";
import { CodeSnippet } from "@/components/white-label/CodeSnippet";
import { HowItWorksAccordion } from "@/components/white-label/HowItWorksAccordion";
import { ArrowLeft } from "lucide-react";

const formSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  source: z.string().min(2, "Source must be at least 2 characters"),
  frontendUrl: z.string().url("Must be a valid URL"),
  clientId: z.string().min(1, "Client ID is required"),
  clientSecret: z.string().min(1, "Client Secret is required"),
});

const CreateWhiteLabel = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [whitelabelGuid, setWhitelabelGuid] = useState<string>("");

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      source: "",
      frontendUrl: "",
      clientId: "",
      clientSecret: "",
    },
  });

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    // In a real app, this would be an API call
    console.log("Submitting:", values);
    const mockGuid = "wl_" + Math.random().toString(36).substr(2, 9);
    setWhitelabelGuid(mockGuid);
    toast({
      title: "Configuration saved",
      description: "Your OAuth2 integration has been configured successfully.",
    });
  };

  const formValues = form.watch();

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/white-label")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Create White Label Integration</h1>
          <p className="text-muted-foreground mt-2">
            Configure a new OAuth2 integration for your application.
          </p>
        </div>
      </div>

      <HowItWorksAccordion />

      <div className="space-y-8">
        <WhiteLabelForm form={form} onSubmit={onSubmit} />

        <CodeSnippet 
          whitelabelGuid={whitelabelGuid}
          frontendUrl={formValues.frontendUrl}
          clientId={formValues.clientId}
          source={formValues.source}
        />

        {whitelabelGuid && (
          <Button onClick={() => navigate(`/white-label/${whitelabelGuid}`)}>
            Go to white label integration
          </Button>
        )}
      </div>
    </div>
  );
};

export default CreateWhiteLabel;