import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { WhiteLabelForm } from "@/components/white-label/WhiteLabelForm";
import { CodeSnippet } from "@/components/white-label/CodeSnippet";
import { HowItWorksAccordion } from "@/components/white-label/HowItWorksAccordion";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface WhiteLabelData {
  id: string;
  name: string;
  source_short_name: string;
  redirect_url: string;
  client_id: string;
}

const CreateWhiteLabel = () => {
  const navigate = useNavigate();
  const [whiteLabel, setWhiteLabel] = useState<WhiteLabelData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSuccess = (data: WhiteLabelData) => {
    setIsLoading(false);
    setWhiteLabel(data);
  };

  // Kick off the OAuth2 flow (matching the snippet in CodeSnippet.tsx)
  const initiateOAuth2Flow = async () => {
    if (!whiteLabel?.id) return;
    try {
      setIsLoading(true);
      const response = await apiClient.get(
        `/connections/oauth2/white-label/${whiteLabel.id}/auth_url`
      );
      if (!response.ok) {
        throw new Error(`Failed to get auth URL. Status: ${response.status}`);
      }
      const authUrl = await response.text();

      // Remove any quotes from the URL and ensure it's a valid URL
      const cleanUrl = authUrl.trim().replace(/^["'](.+)["']$/, '$1');
      if (!cleanUrl.startsWith('http')) {
        throw new Error('Invalid auth URL received');
      }

      // Replace current URL with the OAuth2 URL
      window.location.replace(cleanUrl);

    } catch (error) {
      console.error("Error initiating OAuth2 flow:", error);
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto pb-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/white-label")}>
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
        {/* Form Card */}
        <Card>
          <CardHeader>
            <CardTitle>Integration Configuration</CardTitle>
            <CardDescription>
              Set up your white label integration details. These parameters will be used to generate your integration code.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <WhiteLabelForm onSuccess={handleSuccess} />
          </CardContent>
        </Card>

        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : (
          <>
            {/* Code Snippet Card */}
            <Card className={!whiteLabel?.id ? "opacity-50 pointer-events-none" : ""}>
              <CardHeader>
                <CardTitle>Integration Code</CardTitle>
                <CardDescription>
                  Copy these code snippets to implement the OAuth2 flow in your application.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CodeSnippet
                  whitelabelGuid={whiteLabel?.id}
                  frontendUrl={whiteLabel?.redirect_url}
                  clientId={whiteLabel?.client_id}
                  source={whiteLabel?.source_short_name}
                />
              </CardContent>
            </Card>

            {/* Try Now Card */}
            <Card className={!whiteLabel?.id ? "opacity-50 pointer-events-none" : ""}>
              <CardHeader>
                <CardTitle>Test Your Integration</CardTitle>
                <CardDescription>
                  Try out the OAuth2 flow with your new integration.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p>
                  Click the button below to test the OAuth2 flow with your new integration.
                  This will redirect you to the authentication page.
                </p>
                <Button
                  onClick={initiateOAuth2Flow}
                  disabled={!whiteLabel?.id}
                  className="flex items-center gap-2"
                >
                  <span>Try OAuth2 Flow</span>
                  <ExternalLink className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          </>
        )}

        {whiteLabel && (
          <div className="flex gap-4 pt-4">
            <Button onClick={() => navigate(`/white-label/${whiteLabel.id}`)}>
              Go to integration dashboard
            </Button>
            <Button onClick={() => navigate("/white-label")} variant="outline">
              Back to list
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateWhiteLabel;
