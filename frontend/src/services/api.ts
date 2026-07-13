import type { ChatRequest, ChatResponse } from "@/types";

const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL || "").trim();
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/$/, "").replace(/\/api$/, "");

const buildApiUrl = (path: string) => `${API_BASE_URL}${path}`;

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
};
