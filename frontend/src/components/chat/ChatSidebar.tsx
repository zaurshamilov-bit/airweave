import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusCircle, Search, MessageSquare, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { CreateChatDialog } from "./CreateChatDialog";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface Chat {
  id: string;
  name: string;
  description?: string;
  messages: Array<{
    content: string;
    role: "user" | "assistant";
  }>;
  created_at: string;
  modified_at: string;
}

export const ChatSidebar = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [chats, setChats] = useState<Chat[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    void loadChats();
  }, []);

  async function loadChats() {
    try {
      setIsLoading(true);
      const response = await apiClient.get("/chat");
      const data = await response.json();
      setChats(data);
    } catch (error) {
      console.error("Failed to load chats:", error);
      toast({
        title: "Error",
        description: "Failed to load chats. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }

  const filteredChats = chats
    .sort((a, b) => new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime())
    .filter(
      (chat) =>
        chat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        chat.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

  function handleNewChatCreated(newChatId: string) {
    void loadChats(); // Refresh the chat list
    navigate(`/chat/${newChatId}`);
  }

  return (
    <div className="w-[300px] h-full border-r bg-muted/10">
      <div className="p-4 space-y-4">
        <CreateChatDialog
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
          onChatCreated={handleNewChatCreated}
        />

        <Button
          className="w-full justify-start space-x-2"
          variant="outline"
          onClick={() => setCreateDialogOpen(true)}
        >
          <PlusCircle className="h-4 w-4" />
          <span>New Chat</span>
        </Button>

        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search chats..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <ScrollArea className="h-[calc(100vh-180px)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {filteredChats.length === 0 && !isLoading && (
                <div className="text-center text-sm text-muted-foreground py-4">
                  No chats found
                </div>
              )}
              {filteredChats.map((chat) => (
                <Button
                  key={chat.id}
                  variant="ghost"
                  className={cn(
                    "w-full justify-start text-left space-x-2 h-auto py-3",
                    "hover:bg-accent hover:text-accent-foreground"
                  )}
                  onClick={() => navigate(`/chat/${chat.id}`)}
                >
                  <MessageSquare className="h-4 w-4 shrink-0" />
                  <div className="flex-1 overflow-hidden">
                    <p className="font-medium truncate">
                      {chat.name || "Untitled Chat"}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {chat.messages?.[chat.messages.length - 1]?.content || 
                       chat.description || 
                       "No messages yet"}
                    </p>
                  </div>
                </Button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
};