export interface Source {
  source: string;
  content: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  booking_url?: string | null;
  meeting_url?: string | null;
  owner_email?: string | null;
  interviewer_email?: string | null;
  timestamp: Date;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  booking_url?: string | null;
  meeting_url?: string | null;
  owner_email?: string | null;
  interviewer_email?: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}
