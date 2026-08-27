import { useState } from "react";
import { Check, Copy, Sparkles, TriangleAlert, User } from "lucide-react";
import Markdown from "./Markdown";

export default function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 1500);
    } catch (error) {
      console.error("Failed to copy message:", error);
    }
  }

  return (
    <div
      className={`flex w-full gap-3 animate-fade-up ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-ink-800 text-white"
            : "bg-brand-500 text-white shadow-panel"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
      </div>

      {/* Message Content */}

      <div
        className={`group min-w-0 ${
          isUser
            ? "flex w-full justify-end"
            : "w-full max-w-275"
        }`}
      >

        {/* Loading state */}
        {message.pending && !message.content ? (
          <div className="flex items-center gap-1 py-2">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300 [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300 [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300" />
          </div>
        ) : isUser ? (
          /* User message */
          <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand-500 px-4 py-2.5 text-[0.9375rem] leading-relaxed text-white shadow-sm sm:max-w-[75%]">
            <p className="whitespace-pre-wrap wrap-break-word">
              {message.content}
            </p>
          </div>
        ) : (
          /* Assistant message */
          <div
            className={`w-full min-w-0 ${
              message.failed ? "border-l-2 border-red-400 pl-3" : ""
            }`}
          >
            {/* Error message */}
            {message.failed && (
              <div className="mb-3 flex items-center gap-1.5 text-xs font-medium text-red-600">
                <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                <span>Something went wrong while generating this response.</span>
              </div>
            )}

            {/* Assistant response */}
            <div className="min-w-0 max-w-none">
              <Markdown content={message.content} />
            </div>

            {/* Copy entire response */}
            {message.content && !message.pending && (
              <button
                onClick={handleCopy}
                type="button"
                className="mt-2 flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-ink-400 opacity-0 transition-all hover:bg-ink-100 hover:text-ink-700 group-hover:opacity-100 focus:opacity-100"
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}

                {copied ? "Copied" : "Copy"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}