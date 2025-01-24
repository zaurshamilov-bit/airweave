import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { useLocation } from "react-router-dom";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { dataSources } from "@/config/dataSources";

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
}

const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const { toast } = useToast();
  const location = useLocation();

  const handleSubmit = useCallback(async (content: string, attachments: string[]) => {
    const userMessage: Message = {
      role: "user",
      content,
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Simulate API response
      await new Promise((resolve) => setTimeout(resolve, 1500));

      const botResponse: Message = {
        role: "assistant",
        content: `Based on the search across selected sources, here are the relevant results:\n\n1. Found matching documents discussing this topic.\n2. The documents suggest this functionality is implemented in the core module.\n3. There are related references in the documentation section.`,
      };

      setMessages((prev) => [...prev, botResponse]);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to get a response. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    const state = location.state as { initialMessage?: string; selectedSources?: string[] };
    if (state?.selectedSources) {
      setSelectedSources(state.selectedSources);
    }
    if (state?.initialMessage) {
      void handleSubmit(state.initialMessage, []);
    }
  }, [location.state, handleSubmit, setSelectedSources]);

  const handleSourceChange = (sourceId: string) => {
    setSelectedSources((prev) => {
      if (prev.includes(sourceId)) {
        return prev.filter((id) => id !== sourceId);
      }
      return [...prev, sourceId];
    });
  };

  return (
    <div className="flex h-screen bg-background">
      <ChatSidebar />
      
      <div className="flex-1 flex flex-col">
        <div className="border-b p-4">
          <Select>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select data sources to chat with" />
            </SelectTrigger>
            <SelectContent>
              {dataSources.map((source) => (
                <SelectItem
                  key={source.id}
                  value={source.id}
                  onSelect={() => handleSourceChange(source.id)}
                  className={selectedSources.includes(source.id) ? "bg-primary/10" : ""}
                >
                  <div className="flex items-center gap-2">
                    <img
                      src={`/src/components/icons/apps/${source.short_name}.svg`}
                      className="h-4 w-4"
                      alt={source.name}
                    />
                    <span>{source.name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <ChatMessage key={index} {...message} />
          ))}
        </div>

        <Card className="m-4 p-4">
          <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
        </Card>
      </div>
    </div>
  );
};

export default Chat;