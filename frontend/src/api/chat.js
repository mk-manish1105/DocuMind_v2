import { apiClient, API_BASE_URL, TOKEN_KEY } from "./client";

export async function listSessions() {
  const { data } = await apiClient.get("/chat/sessions");
  return data;
}

export async function renameSession(id, title) {
  const { data } = await apiClient.patch(
    `/chat/sessions/${id}`,
    { title }
  );

  return data;
}

export async function deleteSession(id) {
  const { data } = await apiClient.delete(
    `/chat/sessions/${id}`
  );

  return data;
}

export async function fetchHistory(sessionId) {
  const { data } = await apiClient.get(
    `/chat/history/${sessionId}`
  );

  return data;
}

/**
 * Stream a chat response.
 *
 * Permanent document mode:
 *   question only
 *
 * Temporary document mode:
 *   question + actual File object
 *
 * The temporary file is sent directly to /chat.
 * It is NOT sent through /documents/upload.
 */
export async function streamChatMessage({
  question,
  sessionId,
  attachmentFile,
  onToken,
  signal,
}) {
  const token = localStorage.getItem(TOKEN_KEY);

  const formData = new FormData();

  formData.append(
    "question",
    question
  );

  if (
    sessionId !== null &&
    sessionId !== undefined
  ) {
    formData.append(
      "session_id",
      String(sessionId)
    );
  }

  if (attachmentFile) {
    formData.append(
      "file",
      attachmentFile,
      attachmentFile.name
    );
  }

  formData.append(
    "max_tokens",
    "1600"
  );

  const response = await fetch(
    `${API_BASE_URL}/chat`,
    {
      method: "POST",

      headers: {
        // IMPORTANT:
        // Do NOT set Content-Type manually.
        //
        // Browser automatically creates:
        // multipart/form-data; boundary=...
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },

      body: formData,

      signal,
    }
  );

  if (!response.ok || !response.body) {
    let message =
      "The assistant is temporarily unavailable. Please try again.";

    try {
      const data = await response.json();

      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      // Keep default message.
    }

    const error = new Error(message);
    error.status = response.status;

    throw error;
  }

  const newSessionId =
    response.headers.get(
      "X-Session-Id"
    );

  const reader =
    response.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";

  while (true) {
    const {
      value,
      done,
    } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true,
      }
    );

    let newlineIndex;

    while (
      (newlineIndex =
        buffer.indexOf("\n")) !== -1
    ) {
      const line = buffer
        .slice(0, newlineIndex)
        .trim();

      buffer =
        buffer.slice(
          newlineIndex + 1
        );

      if (!line) {
        continue;
      }

      try {
        const parsed =
          JSON.parse(line);

        if (
          parsed.content
        ) {
          onToken(
            parsed.content
          );
        }
      } catch {
        // Ignore malformed NDJSON lines.
      }
    }
  }

  return newSessionId
    ? Number(newSessionId)
    : null;
}