import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatInfoSidebar } from "@/components/chat/ChatInfoSidebar";
import { ChatInfo, ModelSettings } from "@/components/chat/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { API_CONFIG, apiClient } from "@/lib/api";
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { CreateChatDialog } from "@/components/chat/CreateChatDialog";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  id: number;
}


function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [chatInfo, setChatInfo] = useState<ChatInfo | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  // If you're using a route param like /chat/:chatId
  const { chatId } = useParams<{ chatId: string }>();

  // Check for chatId and load first chat if needed
  useEffect(() => {
    async function initializeChat() {
      try {
        // Use the same endpoint as ChatSidebar
        const response = await apiClient.get('/chat');
        const chats = await response.json();

        if (chats && chats.length > 0) {
          // If we don't have a chatId, navigate to the most recent chat
          if (!chatId) {
            const mostRecentChat = chats.sort((a: Chat, b: Chat) => 
              new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
            )[0];
            navigate(`/chat/${mostRecentChat.id}`);
          }
        } else if (!chatId) {
          // Only show create dialog if there are no chats AND no chatId
          setShowCreateDialog(true);
        }
      } catch (error) {
        console.error("Failed to initialize chat:", error);
        toast({
          title: "Error",
          description: "Failed to load chats. Please try again.",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    }

    void initializeChat();
  }, [chatId, navigate, toast]);

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
          id: Date.now(),
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

      try {
        // Send user message
        await apiClient.post(`/chat/${chatId}/message`, {
          content,
          role: "user",
        });

        // Add user message to UI
        setMessages(prev => [...prev, { role: "user", content, id: Date.now() }]);

        // Start stream
        const response = await fetch(`${API_CONFIG.baseURL}/chat/${chatId}/stream`, {
          method: 'GET',
          credentials: 'include',
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        if (!reader) throw new Error('No reader available');

        // Create ONE assistant message
        const assistantMessage = { role: "assistant" as const, content: "", id: Date.now() };
        setMessages(prev => [...prev, assistantMessage]);

        // Stream the response
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const content = line.slice(6);
              
              if (content === '[DONE]' || content === '[ERROR]') {
                setIsLoading(false);
                break;
              }
              
              console.log('Content chunk:', JSON.stringify(content));
              
              // Handle empty strings as newlines
              if (content === "") {
                assistantMessage.content += "\n";
              } else {
                assistantMessage.content += content;
              }
              setMessages(prev => [...prev]);  // Force re-render
            }
          }
        }
      } catch (error) {
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

  useEffect(() => {
    if (chatId) {
      void loadChatInfo();
    }
  }, [chatId]);

  const loadChatInfo = async () => {
    try {
      // Get chat info
      const chatResponse = await apiClient.get(`/chat/${chatId}`);
      const chatData = await chatResponse.json();
      
      // Get sync info
      const syncResponse = await apiClient.get(`/sync/${chatData.sync_id}`);
      const syncData = await syncResponse.json();

      // Get source connection
      const sourceConnResponse = await apiClient.get(`/connections/detail/${syncData.source_connection_id}`);
      const sourceConnData = await sourceConnResponse.json();
      
      // Get source details
      const sourceResponse = await apiClient.get(`/sources/detail/${sourceConnData.short_name}`);
      const sourceData = await sourceResponse.json();

      // Get destination connection and details if exists
      let destinationConnData = null;
      let destinationData = null;
      
      if (syncData.destination_connection_id) {
        const destConnResponse = await apiClient.get(`/connections/detail/${syncData.destination_connection_id}`);
        destinationConnData = await destConnResponse.json();
        
        const destResponse = await apiClient.get(`/destinations/detail/${destinationConnData.short_name}`);
        destinationData = await destResponse.json();
      }
      
      // Combine all the data
      setChatInfo({
        ...chatData,
        sync: {
          ...syncData,
          source_connection: {
            ...sourceConnData,
            source: sourceData
          },
          destination_connection: destinationConnData ? {
            ...destinationConnData,
            destination: destinationData
          } : null
        }
      });
    } catch (error) {
      console.error("Failed to load chat info:", error);
    }
  };

  const handleUpdateSettings = async (settings: Partial<ModelSettings>) => {
    if (!chatId) return;
      
    const response = await apiClient.put(`/chat/${chatId}`, undefined, {
      model_settings: settings,  // Pass undefined for params, then the data
    });
    
    if (response.ok) {
      await loadChatInfo();
    } else {
      toast({
        title: "Error",
        description: "Failed to update settings",
        variant: "destructive",
      });
    }
  };

  // Check location state for create dialog and preselected sync
  useEffect(() => {
    const state = location.state as { 
      showCreateDialog?: boolean;
      preselectedSyncId?: string;
    };
    
    if (state?.showCreateDialog) {
      setShowCreateDialog(true);
    }
  }, [location.state]);

  return (
    <div className="flex h-full">
      <ChatSidebar onCreateChat={() => setShowCreateDialog(true)} />
      <div className="flex-1 flex flex-col">
        {showCreateDialog ? (
          <CreateChatDialog 
            open={showCreateDialog}
            preselectedSyncId={location.state?.preselectedSyncId}
            onOpenChange={(open) => {
              setShowCreateDialog(open);
              if (!open) {
                navigate(location.pathname, { replace: true });
              }
              if (!open && !chatId) {
                navigate('/dashboard');
              }
            }}
            onChatCreated={(newChatId) => {
              setShowCreateDialog(false);
              navigate(`/chat/${newChatId}`);
            }}
          />
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((message, index) => (
                <div key={index} className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}>
                  <div className={cn(
                    "max-w-[80%]",
                    message.role === "user" ? "ml-auto" : "mr-auto"
                  )}>
                    <ChatMessage
                      role={message.role}
                      content={message.content}
                      attachments={message.attachments}
                    />
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-center">
                  <Spinner className="h-6 w-6" />
                </div>
              )}
            </div>
            <Card className="m-4 p-4">
              <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
            </Card>
          </>
        )}
      </div>
      {chatInfo && (
        <ChatInfoSidebar
          chatInfo={chatInfo}
          onUpdateSettings={handleUpdateSettings}
        />
      )}
    </div>
  );
}

export default Chat;