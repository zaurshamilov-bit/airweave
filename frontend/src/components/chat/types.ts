interface Chat {
  id: string;
  name: string;
  sync_id: string;
  description?: string;
  messages: ChatMessage[];
  created_at: string;
  modified_at: string;
}

interface ChatMessage {
  id: string;
  chat_id: string;
  content: string;
  role: "user" | "assistant";
  created_at: string;
  attachments?: string[];
}