import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { BookCallModal } from "./BookCallModal";
import type { ChatMessage } from "@/types";
import { chatAPI } from "@/services/api";

interface ChatTheme {
  name: string;
  label: string;
  background: string;
  shell: string;
  shellBorder: string;
  shellShadow: string;
  card: string;
  cardBorder: string;
  cardShadow: string;
  insetShadow: string;
  text: string;
  muted: string;
  accent: string;
  accentSoft: string;
  accentTwo: string;
  inputBg: string;
  assistantBg: string;
  assistantText: string;
  userBg: string;
  userText: string;
  online: string;
  blobA: string;
  blobB: string;
}

interface ChatContainerProps {
  theme: ChatTheme;
  onThemeChange: (theme: "light" | "dark" | "purple") => void;
}

const SUGGESTED_PROMPTS = [
  "Tell me about NavDrishti",
  "Show me your projects",
  "What are your achievements?",
  "What skills do you bring?",
  "Book a slot",
];

const VAPI_PHONE_NUMBER = "+1 (346) 363-6616";

export function ChatContainer({ theme, onThemeChange }: ChatContainerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showBookCallModal, setShowBookCallModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    setError(null);

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await chatAPI.sendMessage(content);

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        booking_url: response.booking_url,
        meeting_url: response.meeting_url,
        owner_email: response.owner_email,
        interviewer_email: response.interviewer_email,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
      console.error("Chat error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  const handleSuggestedPrompt = (prompt: string) => {
    if (prompt === "Book a slot") {
      setShowBookCallModal(true);
    } else {
      handleSendMessage(prompt);
    }
  };

  return (
    <div
      className="flex h-[92vh] max-h-[900px] flex-col overflow-hidden rounded-[32px] border p-2 shadow-[12px_12px_24px_rgba(15,23,42,0.10)] backdrop-blur-xl"
      style={{
        background: theme.shell,
        borderColor: `${theme.accent}20`,
        boxShadow: `${theme.shellShadow}, inset 0 0 0 1px ${theme.accent}10`,
      }}
    >
      <div
        className="sticky top-0 z-10 flex items-center justify-between border-b px-4 py-4 sm:px-5"
        style={{ borderColor: `${theme.accent}18`, background: `${theme.shell}f0` }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-[20px] text-lg font-semibold"
            style={{ background: theme.accentSoft, color: theme.accent, boxShadow: theme.insetShadow }}
          >
            S
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold" style={{ color: theme.text }}>
                Shubham AI
              </h1>
              <span className="inline-flex h-2.5 w-2.5 rounded-full" style={{ background: theme.online }} />
            </div>
            <p className="text-sm" style={{ color: theme.muted }}>
              AI Representative · Online
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-full border p-1" style={{ borderColor: `${theme.accent}18`, background: theme.card }}>
            {(["light", "dark"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => onThemeChange(option)}
                className="rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-all"
                style={{
                  background: theme.name === option ? theme.accentSoft : "transparent",
                  color: theme.name === option ? theme.accent : theme.muted,
                  border: theme.name === option ? `1px solid ${theme.accent}20` : "1px solid transparent",
                }}
              >
                {option === "light" ? "☀️" : "🌙"}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={handleClearChat}
            disabled={messages.length === 0}
            className="rounded-full border px-3 py-2 text-sm transition-all disabled:cursor-not-allowed disabled:opacity-50"
            style={{ borderColor: theme.cardBorder, color: theme.muted, background: theme.card }}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 sm:px-4 sm:py-5">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex h-full flex-col justify-center"
          >
            <div
              className="mx-auto flex w-full max-w-[360px] flex-col items-center rounded-[28px] border px-6 py-8 text-center"
              style={{ background: theme.card, borderColor: `${theme.accent}16`, boxShadow: `${theme.cardShadow}, inset 0 0 0 1px ${theme.accent}08` }}
            >
              <div
                className="mb-5 flex h-20 w-20 items-center justify-center rounded-[24px] text-3xl"
                style={{ background: theme.accentSoft, boxShadow: theme.insetShadow }}
              >
                🤖
              </div>
              <h2 className="text-2xl font-semibold" style={{ color: theme.text }}>
                Hi, I&apos;m Shubham&apos;s AI Assistant
              </h2>
              <p className="mt-2 text-sm leading-6" style={{ color: theme.muted }}>
                Ask me anything about my projects, skills, internships and experience.
              </p>

              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt, index) => (
                  <motion.button
                    key={prompt}
                    type="button"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.06 }}
                    whileHover={{ y: -2, scale: 1.01 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => handleSuggestedPrompt(prompt)}
                    disabled={loading}
                    className="rounded-full border px-3 py-2 text-sm transition-all disabled:cursor-not-allowed disabled:opacity-60"
                    style={{ borderColor: theme.cardBorder, color: theme.text, background: theme.inputBg }}
                  >
                    {prompt}
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="mx-auto max-w-[520px]">
            <AnimatePresence initial={false}>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} theme={theme} />
              ))}
            </AnimatePresence>

            {loading && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 flex items-center gap-2 rounded-[22px] px-4 py-3 text-sm"
                style={{ background: theme.card, color: theme.muted, boxShadow: theme.cardShadow }}
              >
                <span className="font-medium">Thinking</span>
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" />
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "0.16s" }} />
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "0.32s" }} />
                </span>
              </motion.div>
            )}

            {error && (
              <div className="rounded-[20px] border px-4 py-3 text-sm" style={{ background: "rgba(248,113,113,0.12)", borderColor: "rgba(248,113,113,0.24)", color: "#b91c1c" }}>
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="border-t px-3 py-3 sm:px-4 sm:py-4" style={{ borderColor: `${theme.accent}18` }}>
          <div className="mx-auto max-w-[520px]">
          <ChatInput onSubmit={handleSendMessage} disabled={loading} theme={theme} onBookCall={() => setShowBookCallModal(true)} />
        </div>
      </div>

      <BookCallModal
        isOpen={showBookCallModal}
        onClose={() => setShowBookCallModal(false)}
        phoneNumber={VAPI_PHONE_NUMBER}
        theme={{
          text: theme.text,
          background: theme.background,
          card: theme.card,
          cardBorder: theme.cardBorder,
          accent: theme.accent,
          inputBg: theme.inputBg,
        }}
      />
    </div>
  );
}
