import type { ChatRequest, ChatResponse, Source } from "@/types";

const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL || "").trim();
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/$/, "").replace(/\/api$/, "");

const buildApiUrl = (path: string) => `${API_BASE_URL}${path}`;

function parseSSE(raw: string) {
  const lines = raw.split(/\r?\n/).filter(Boolean);
  const dataLines = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());
  if (dataLines.length === 0) {
    return null;
  }
  try {
    return JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }
}

export const chatAPI = {
  async sendMessage(message: string): Promise<ChatResponse> {
    const response = await fetch(buildApiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message } as ChatRequest),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json() as Promise<ChatResponse>;
  },

  async sendMessageStream(
    message: string,
    onDelta: (delta: string) => void,
    onDone: (payload: {
      sources?: Source[];
      booking_url?: string | null;
      meeting_url?: string | null;
      owner_email?: string | null;
      interviewer_email?: string | null;
    }) => void,
  ): Promise<void> {
    const response = await fetch(buildApiUrl("/api/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message } as ChatRequest),
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API error: ${response.statusText} ${errorText}`);
    }

    if (!response.body) {
      throw new Error("Stream unavailable");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      let boundaryIndex = buffer.indexOf("\n\n");
      while (boundaryIndex !== -1) {
        const chunk = buffer.slice(0, boundaryIndex);
        buffer = buffer.slice(boundaryIndex + 2);
        boundaryIndex = buffer.indexOf("\n\n");

        const event = parseSSE(chunk);
        if (!event) {
          continue;
        }

        if (event.type === "delta") {
          onDelta(event.text || "");
        } else if (event.type === "done") {
          onDone({
            sources: event.sources || [],
            booking_url: event.booking_url ?? null,
            meeting_url: event.meeting_url ?? null,
            owner_email: event.owner_email ?? null,
            interviewer_email: event.interviewer_email ?? null,
          });
        } else if (event.type === "error") {
          throw new Error(event.message || "Stream error");
        }
      }
    }
  },
};
