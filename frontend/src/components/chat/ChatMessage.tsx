import React from "react";
import { ImageModal } from "./ImageModal";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

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
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          className="prose dark:prose-invert max-w-none"
          components={{
            code({node, inline, className, children, ...props}) {
              const match = /language-(\w+)/.exec(className || '');
              return !inline && match ? (
                <SyntaxHighlighter
                  {...props}
                  style={vscDarkPlus}
                  language={match[1]}
                  PreTag="div"
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : (
                <code {...props} className={className}>
                  {children}
                </code>
              );
            }
          }}
        >
          {content}
        </ReactMarkdown>
        {attachments?.length > 0 && (
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