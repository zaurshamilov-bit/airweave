import React from "react";
import { ImageModal } from "./ImageModal";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
}

export const ChatMessage = ({ role, content, attachments }: ChatMessageProps) => {
  const [selectedImage, setSelectedImage] = React.useState<string | null>(null);

  return (
    <div className={`flex ${role === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg p-4 ${
          role === "user"
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        }`}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        {attachments && attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {attachments.map((file, i) => (
              file.startsWith('data:image') ? (
                <img
                  key={i}
                  src={file}
                  alt={`Attachment ${i + 1}`}
                  className="w-24 h-24 object-cover rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                  onClick={() => setSelectedImage(file)}
                />
              ) : (
                <div key={i} className="flex items-center gap-1">
                  <span className="text-sm opacity-80">{file}</span>
                </div>
              )
            ))}
          </div>
        )}
      </div>
      <ImageModal
        isOpen={!!selectedImage}
        image={selectedImage}
        onClose={() => setSelectedImage(null)}
      />
    </div>
  );
};