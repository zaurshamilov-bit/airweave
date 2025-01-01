import { UseFormReturn } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dataSources } from "@/config/dataSources";
import * as z from "zod";
import { ComponentType } from "react";
import { getAppIconUrl } from "@/lib/utils/icons";

const formSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  source: z.string().min(2, "Source must be at least 2 characters"),
  frontendUrl: z.string().url("Must be a valid URL"),
  clientId: z.string().min(1, "Client ID is required"),
  clientSecret: z.string().min(1, "Client Secret is required"),
});

interface WhiteLabelFormProps {
  form: UseFormReturn<z.infer<typeof formSchema>>;
  onSubmit: (values: z.infer<typeof formSchema>) => Promise<void>;
}

export const WhiteLabelForm = ({ form, onSubmit }: WhiteLabelFormProps) => {
  const selectedSource = form.watch("source");
  const selectedSourceData = dataSources.find(
    (source) => source.id === selectedSource
  );

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Integration Name</FormLabel>
              <FormControl>
                <Input placeholder="My Integration" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="source"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Source</FormLabel>
              <FormControl>
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a data source" />
                  </SelectTrigger>
                  <SelectContent>
                    {dataSources.map((source) => (
                      <SelectItem
                        key={source.id}
                        value={source.id}
                        className="flex items-center"
                      >
                        <div className="flex items-center gap-2">
                          <img
                            src={getAppIconUrl(source.short_name)}
                            className="h-4 w-4 mr-2"
                            alt={source.name}
                          />
                          <span>{source.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {selectedSourceData && (
          <div className="bg-secondary/10 p-4 rounded-lg space-y-2">
            <h3 className="font-medium">
              Setup Instructions for {selectedSourceData.name}
            </h3>
            <ol className="list-decimal list-inside space-y-2 text-sm">
              <li>Go to your {selectedSourceData.name} Developer Console</li>
              <li>Create a new OAuth2 application</li>
              <li>Set the callback URL to your frontend URL</li>
              <li>Copy the Client ID and Client Secret</li>
              <li>Fill out the form below with your application details</li>
            </ol>
          </div>
        )}

        <FormField
          control={form.control}
          name="frontendUrl"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Frontend Callback URL</FormLabel>
              <FormControl>
                <Input
                  placeholder="https://your-app.com/oauth/callback"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="clientId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Client ID</FormLabel>
              <FormControl>
                <Input placeholder="Your OAuth2 Client ID" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="clientSecret"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Client Secret</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  placeholder="Your OAuth2 Client Secret"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit">Save Configuration</Button>
      </form>
    </Form>
  );
};
