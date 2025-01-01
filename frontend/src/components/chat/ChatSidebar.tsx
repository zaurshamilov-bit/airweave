import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusCircle, Search, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatHistory {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
}

export const ChatSidebar = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [chats] = useState<ChatHistory[]>([
    {
      id: "1",
      title: "Notion Integration Setup",
      preview: "How do I configure the Notion integration?",
      timestamp: new Date(2024, 1, 15),
    },
    {
      id: "2",
      title: "Data Synchronization",
      preview: "Tell me about sync schedules",
      timestamp: new Date(2024, 1, 14),
    },
    // Add more mock chats as needed
  ]);

  const filteredChats = chats.filter(
    (chat) =>
      chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.preview.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="w-[300px] h-full border-r bg-muted/10">
      <div className="p-4 space-y-4">
        <Button className="w-full justify-start space-x-2" variant="outline">
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
          <div className="space-y-2">
            {filteredChats.map((chat) => (
              <Button
                key={chat.id}
                variant="ghost"
                className={cn(
                  "w-full justify-start text-left space-x-2 h-auto py-3",
                  "hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 overflow-hidden">
                  <p className="font-medium truncate">{chat.title}</p>
                  <p className="text-xs text-muted-foreground truncate">
                    {chat.preview}
                  </p>
                </div>
              </Button>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
};