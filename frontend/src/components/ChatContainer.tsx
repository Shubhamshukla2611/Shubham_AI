import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { BookCallModal } from "./BookCallModal";
import ShapeBlur from "./ShapeBlur";
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
  strandColors: string[];
  strandOpacity: number;
}

type ThemeName = "light" | "dark" | "purple";

interface ChatContainerProps {
  theme: ChatTheme;
  onThemeChange: (theme: ThemeName) => void;
}

const SUGGESTED_PROMPTS = [
  "Tell me about NavDrishti",
  "Show me your projects",
  "What are your achievements?",
  "What skills do you bring?",
  "Book a slot",
];

const VAPI_PHONE_NUMBER = "+1 (346) 363-6616";

/**
 * Interactive cursor-following glow. Renders a transparent ShapeBlur
 * overlay whose `u_mouse` tracks the pointer. Disabled on coarse /
 * touch-only pointers so it never fights a thumb, and clipped to the
 * container so the glow can't leak past the chat shell.
 *
 * The layer is `pointer-events-none` so it never blocks clicks; the
 * actual hit testing happens on the elements underneath.
 */
function HoverGlow({ accent, enabled }: { accent: string; enabled: boolean }) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [isFine, setIsFine] = useState(false);
  const [variant, setVariant] = useState<0 | 1 | 2 | 3>(0);

  // Pick the ShapeBlur shape per theme so dark/purple/light get
  // slightly different silhouettes, and only enable on devices that
  // have a precise pointer (no hover glow on phones / tablets).
  useEffect(() => {
    const mq = window.matchMedia("(hover: hover) and (pointer: fine)");
    setIsFine(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setIsFine(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    setVariant(enabled ? 0 : 3);
  }, [enabled]);

  if (!isFine) return null;

  return (
    <div
      ref={wrapperRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
      style={{ mixBlendMode: "screen" }}
    >
      {/* ShapeBlur uses a `document` mousemove listener to compute u_mouse,
          but its WebGL output is sized to its own bounding box. The
          cursor coords are mapped to (mountX, mountY) inside the shader
          automatically, so as long as the wrapper covers the chat
          shell, the glow follows the pointer correctly. */}
      <div
        className="absolute inset-0"
        style={{
          opacity: enabled ? 0.85 : 0,
          transition: "opacity 400ms ease",
          // The shader outputs pure white; the wrapper tints the result
          // through blend-mode + a faint accent wash via a CSS overlay.
        }}
      >
        <ShapeBlur
          variation={variant}
          pixelRatioProp={Math.min(window.devicePixelRatio || 1, 2)}
          shapeSize={0.6}
          roundness={0.5}
          borderSize={0.05}
          circleSize={0.4}
          circleEdge={0.5}
        />
      </div>
      {/* A subtle accent-tinted wash on top of the white ShapeBlur
          output, so the glow picks up the theme colour instead of
          being a flat white halo. */}
      <div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(circle at 50% 50%, ${accent}55 0%, transparent 60%)`,
          mixBlendMode: "multiply",
        }}
      />
    </div>
  );
}

export function ChatContainer({ theme, onThemeChange }: ChatContainerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showBookCallModal, setShowBookCallModal] = useState(false);
  const [hoverActive, setHoverActive] = useState(false);
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
      className="relative flex h-[100dvh] flex-col overflow-hidden rounded-none border p-1.5 shadow-[12px_12px_24px_rgba(15,23,42,0.10)] backdrop-blur-xl sm:h-[92vh] sm:max-h-[900px] sm:rounded-[32px] sm:p-2"
      style={{
        background: theme.shell,
        borderColor: `${theme.accent}20`,
        boxShadow: `${theme.shellShadow}, inset 0 0 0 1px ${theme.accent}10`,
      }}
      onMouseEnter={() => setHoverActive(true)}
      onMouseLeave={() => setHoverActive(false)}
    >
      {/* Mouse-following glow that tracks the pointer inside the chat
          shell. The ShapeBlur output is white; a CSS tint on top makes
          it pick up the theme accent. Disabled on touch / coarse
          pointers inside HoverGlow itself. */}
      <HoverGlow accent={theme.accent} enabled={hoverActive} />

      <div
        className="sticky top-0 z-20 flex items-center justify-between border-b px-3 py-3 sm:px-5 sm:py-4"
        style={{ borderColor: `${theme.accent}18`, background: `${theme.shell}f0` }}
      >
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[16px] text-base font-semibold sm:h-12 sm:w-12 sm:rounded-[20px] sm:text-lg"
            style={{ background: theme.accentSoft, color: theme.accent, boxShadow: theme.insetShadow }}
          >
            S
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 sm:gap-2">
              <h1 className="truncate text-base font-semibold sm:text-lg" style={{ color: theme.text }}>
                Shubham AI
              </h1>
              <span className="inline-flex h-2 w-2 shrink-0 rounded-full sm:h-2.5 sm:w-2.5" style={{ background: theme.online }} />
            </div>
            <p className="hidden truncate text-[11px] sm:block sm:text-sm" style={{ color: theme.muted }}>
              AI Representative · Online
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <div className="flex items-center gap-0.5 rounded-full border p-0.5 sm:gap-1 sm:p-1" style={{ borderColor: `${theme.accent}18`, background: theme.card }}>
            {(
              [
                { id: "light", label: "Light theme", icon: "☀️" },
                { id: "purple", label: "Purple theme", icon: "💜" },
                { id: "dark", label: "Dark theme", icon: "🌙" },
              ] as const
            ).map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => onThemeChange(option.id)}
                aria-label={option.label}
                className="rounded-full px-2 py-1 text-[10px] font-medium transition-all sm:px-2.5 sm:py-1.5 sm:text-[11px]"
                style={{
                  background: theme.name === option.id ? theme.accentSoft : "transparent",
                  color: theme.name === option.id ? theme.accent : theme.muted,
                  border: theme.name === option.id ? `1px solid ${theme.accent}20` : "1px solid transparent",
                }}
              >
                {option.icon}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={handleClearChat}
            disabled={messages.length === 0}
            aria-label="Clear chat"
            className="rounded-full border px-2.5 py-1.5 text-xs transition-all disabled:cursor-not-allowed disabled:opacity-50 sm:px-3 sm:py-2 sm:text-sm"
            style={{ borderColor: theme.cardBorder, color: theme.muted, background: theme.card }}
          >
            <span className="sm:hidden">🗑</span>
            <span className="hidden sm:inline">Clear</span>
          </button>
        </div>
      </div>

      <div className="relative z-20 flex-1 overflow-y-auto px-2 py-3 sm:px-4 sm:py-5">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex h-full flex-col justify-center"
          >
            <div
              className="mx-auto flex w-full max-w-[320px] flex-col items-center rounded-[24px] border px-4 py-6 text-center sm:max-w-[360px] sm:rounded-[28px] sm:px-6 sm:py-8"
              style={{ background: theme.card, borderColor: `${theme.accent}16`, boxShadow: `${theme.cardShadow}, inset 0 0 0 1px ${theme.accent}08` }}
            >
              <div
                className="mb-4 flex h-16 w-16 items-center justify-center rounded-[20px] text-2xl sm:mb-5 sm:h-20 sm:w-20 sm:rounded-[24px] sm:text-3xl"
                style={{ background: theme.accentSoft, boxShadow: theme.insetShadow }}
              >
                🤖
              </div>
              <h2 className="text-xl font-semibold sm:text-2xl" style={{ color: theme.text }}>
                Hi, I&apos;m Shubham&apos;s AI Assistant
              </h2>
              <p className="mt-2 text-[13px] leading-5 sm:text-sm sm:leading-6" style={{ color: theme.muted }}>
                Ask me anything about my projects, skills, internships and experience.
              </p>

              <div className="mt-5 flex flex-wrap justify-center gap-1.5 sm:mt-6 sm:gap-2">
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
                    className="rounded-full border px-2.5 py-1.5 text-xs transition-all disabled:cursor-not-allowed disabled:opacity-60 sm:px-3 sm:py-2 sm:text-sm"
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
                className="mb-4 flex items-center gap-2 rounded-[20px] px-3 py-2.5 text-sm sm:rounded-[22px] sm:px-4 sm:py-3"
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

      <div className="relative z-20 safe-bottom border-t px-2 py-2 sm:px-4 sm:py-4" style={{ borderColor: `${theme.accent}18` }}>
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
