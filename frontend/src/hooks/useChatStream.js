import { useRef, useState } from "react";
import { streamChatMessage } from "../api/chat";

const SESSION_CONTEXT_MESSAGE_LIMIT = 4;
const SESSION_MESSAGE_CHAR_LIMIT = 1500;

export function useChatStream({
  messages,
  setMessages,
  sessionId,
  isGuest,
  onSessionCreated,
  onTemporaryAttachmentConsumed,
}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  async function sendMessage(question, attachmentFile = null) {
    setError(null);

    const userMessage = {
      role: "user",
      content: question,
      created_at: new Date().toISOString(),

      // UI metadata only
      attachmentName: attachmentFile?.name || null,
    };

    const assistantMessage = {
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      pending: true,
    };

    // ========================================================
    // GUEST CONVERSATION HISTORY
    //
    // Guests have no persisted server-side chat history, so we
    // build it from the messages already in memory and send it
    // along with the request. This is captured BEFORE the new
    // optimistic messages are appended below, so it reflects
    // only prior turns.
    //
    // This is only ever used for guests — authenticated users
    // always rely on DB-sourced history on the backend.
    // ========================================================

    let historyPayload = null;

    if (isGuest) {
      historyPayload = messages
        .filter((m) => m.content && !m.pending)
        .slice(-SESSION_CONTEXT_MESSAGE_LIMIT)
        .map((m) => ({
          role: m.role,
          content: m.content.slice(0, SESSION_MESSAGE_CHAR_LIMIT),
        }));
    }

    // Functional update avoids stale state
    setMessages((prev) => [
      ...prev,
      userMessage,
      assistantMessage,
    ]);

    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulated = "";

    try {
      const newSessionId = await streamChatMessage({
        question,
        sessionId,
        attachmentFile,
        history: historyPayload,
        signal: controller.signal,

        onToken: (token) => {
          accumulated += token;

          setMessages((prev) => {
            const next = [...prev];

            if (next.length === 0) return next;

            const lastIndex = next.length - 1;

            next[lastIndex] = {
              ...next[lastIndex],
              content: accumulated,
              pending: false,
            };

            return next;
          });
        },
      });

      if (newSessionId && !sessionId) {
        onSessionCreated?.(newSessionId);
      }

      // Remove temporary attachment after successful response
      if (attachmentFile) {
        onTemporaryAttachmentConsumed?.();
      }

    } catch (err) {
      if (err.name !== "AbortError") {
        setError(
          err.message ||
          "The assistant couldn't respond. Please try again."
        );

        setMessages((prev) => {
          const next = [...prev];

          if (next.length === 0) return next;

          const lastIndex = next.length - 1;

          next[lastIndex] = {
            ...next[lastIndex],
            content:
              accumulated ||
              "Sorry, something went wrong generating a response.",
            pending: false,
            failed: true,
          };

          return next;
        });

        // Remove temporary attachment even if backend fails
        if (attachmentFile) {
          onTemporaryAttachmentConsumed?.();
        }
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  return {
    sendMessage,
    stopStreaming,
    isStreaming,
    error,
  };
}