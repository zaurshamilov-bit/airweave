import React, { useEffect, useState, useMemo } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
}

export function ChatMessage({ role, content, attachments }: ChatMessageProps) {
  return (
    <div className={cn(
      "rounded-lg p-4",
      role === "user" ? "bg-primary bg-opacity-80 text-primary-foreground" : "bg-muted"
    )}>
      <div className="prose prose-invert max-w-none whitespace-pre-wrap">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
        >
          {content}
        </ReactMarkdown>
      </div>
      {attachments?.length > 0 && (
        <div className="flex gap-2 mt-2">
          {attachments.map((attachment, index) => (
            <div key={index} className="text-sm text-muted-foreground">
              {attachment}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}