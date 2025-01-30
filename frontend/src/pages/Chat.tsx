import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { API_CONFIG, apiClient } from "@/lib/api";
import { dataSources } from "@/config/dataSources";

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();

  // If you're using a route param like /chat/:chatId
  const { chatId } = useParams<{ chatId: string }>();

  // Load chat data on mount or when chatId changes
  useEffect(() => {
    async function loadChat() {
      if (!chatId) return;
      try {
        setIsLoading(true);
        const resp = await apiClient.get(`/chat/${chatId}`);
        
        console.log("Loading chat data:", resp); // Debug log
        
        // Handle the response data directly
        const chatData = await resp.json();
        
        // Ensure messages is an array, even if empty
        const messages = chatData.messages || [];
        
        setMessages(messages.map((m: any) => ({
          role: m.role || 'user',
          content: m.content,
          attachments: m.attachments || [],
        })));
      } catch (error) {
        console.error("Failed to load chat:", error);
        if (error.response) {
          console.error("Error response:", error.response);
        }
        toast({
          title: "Error",
          description: "Failed to load chat. Please try again.",
          variant: "destructive",
        });
        // Only navigate away if it's a 404
        if (error.response?.status === 404) {
          navigate("/");
        }
      } finally {
        setIsLoading(false);
      }
    }
    void loadChat();
  }, [chatId, navigate, toast]);

  // Auto-run if user came here with an initial message or sources
  useEffect(() => {
    const state = location.state as { initialMessage?: string; selectedSources?: string[] };
    if (state?.selectedSources) {
      setSelectedSources(state.selectedSources);
    }
    if (state?.initialMessage) {
      void handleSubmit(state.initialMessage, []);
    }
  }, [location.state]);

  // Submit a message via SSE endpoint
  const handleSubmit = useCallback(
    async (content: string, attachments: string[]) => {
      if (!chatId) {
        toast({
          title: "Error",
          description: "Chat ID not found. Please create or select a chat first.",
          variant: "destructive",
        });
        return;
      }

      const userMessage: Message = {
        role: "user",
        content,
        attachments: attachments.length > 0 ? attachments : undefined,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        // First, send the message
        await apiClient.post(`/chat/${chatId}/message`, {
          content,
          role: "user",
        });

        // Then, get the streaming response
        const response = await fetch(`${API_CONFIG.baseURL}/chat/${chatId}/stream`, {
          method: 'GET',
          credentials: 'include',
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('No reader available');
        }

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const content = line.slice(6);
              if (content === '[DONE]') {
                setIsLoading(false);
                continue;
              }
              
              setMessages((prev) => {
                const newMessages = [...prev];
                if (!newMessages.length || newMessages[newMessages.length - 1].role !== "assistant") {
                  newMessages.push({ role: "assistant", content: "" });
                }
                newMessages[newMessages.length - 1].content += content;
                return newMessages;
              });
            }
          }
        }
      } catch (error) {
        console.error("Stream Error:", error);
        setIsLoading(false);
        toast({
          title: "Error",
          description: "Failed to get response. Please try again.",
          variant: "destructive",
        });
      }
    },
    [chatId, toast]
  );

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
}

export default Chat;