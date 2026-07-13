import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/types";

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

interface MessageBubbleProps {
  message: ChatMessage;
  theme: ChatTheme;
}

export function MessageBubble({ message, theme }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const formatScore = (score: number) => {
    if (Number.isNaN(score)) {
      return "N/A";
    }

    return `${Math.round(score * 100)}% match`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      className={`mb-5 flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`flex max-w-[92%] gap-2.5 sm:max-w-[82%] ${isUser ? "flex-row-reverse" : "flex-row"}`}
      >
        {/* Avatar */}
        <div
          className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] text-sm font-semibold"
          style={{
            background: isUser
              ? `linear-gradient(135deg, ${theme.accent} 0%, ${theme.accentTwo} 100%)`
              : theme.accentSoft,
            color: isUser ? theme.userText : theme.accent,
            boxShadow: isUser ? "0 8px 20px rgba(109,79,242,0.22)" : theme.insetShadow,
          }}
        >
          {isUser ? "You" : "S"}
        </div>

        <div className={`min-w-0 flex-1 ${isUser ? "text-right" : "text-left"}`}>
          {/* Bubble */}
          <div
            className="inline-block max-w-full rounded-[22px] px-4 py-3.5 text-left sm:px-5"
            style={{
              background: isUser ? theme.userBg : theme.assistantBg,
              color: isUser ? theme.userText : theme.assistantText,
              boxShadow: isUser ? "0 16px 35px rgba(109,79,242,0.22)" : theme.cardShadow,
              border: `1px solid ${isUser ? "rgba(255,255,255,0.18)" : theme.cardBorder}`,
            }}
          >
            {/* Header strip — author + role */}
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em]">
              <span style={{ color: isUser ? theme.userText : theme.text }}>
                {isUser ? "You" : "Shubham's Assistant"}
              </span>
              {!isUser && (
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal"
                  style={{
                    background: theme.accentSoft,
                    color: theme.accent,
                  }}
                >
                  AI · grounded answer
                </span>
              )}
            </div>

            {/* Body */}
            <div
              className="markdown-body break-words text-[14.5px] leading-7"
              style={{ color: isUser ? theme.userText : theme.assistantText }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>

            {/* Sources (assistant only) */}
            {!isUser && message.sources && message.sources.length > 0 && (
              <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
                {message.sources.map((source, idx) => (
                  <div
                    key={idx}
                    className="overflow-hidden rounded-[14px] border p-3 transition duration-200 hover:-translate-y-0.5"
                    style={{ borderColor: theme.cardBorder, background: theme.card }}
                  >
                    <div className="flex items-start gap-2.5">
                      <div
                        className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px] text-xs"
                        style={{ background: theme.accentSoft, color: theme.accent }}
                      >
                        📄
                      </div>
                      <div className="min-w-0 flex-1">
                        <div
                          className="truncate text-[12px] font-semibold"
                          style={{ color: theme.text }}
                        >
                          {source.source}
                        </div>
                        <div
                          className="mt-1.5 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                          style={{
                            borderColor: `${theme.accent}20`,
                            background: theme.accentSoft,
                            color: theme.accent,
                          }}
                        >
                          {formatScore(source.score)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Booking CTA (assistant only) */}
            {!isUser && message.booking_url && (
              <div className="mt-4 space-y-2">
                <a
                  href={message.booking_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all hover:-translate-y-0.5"
                  style={{
                    borderColor: `${theme.accent}20`,
                    background: theme.accentSoft,
                    color: theme.accent,
                  }}
                >
                  <span>📅</span>
                  Book via Google Calendar
                </a>
                <p className="text-[11px]" style={{ color: theme.muted }}>
                  After you choose a slot, the invite should be shared with Shubham and the interviewer.
                </p>
              </div>
            )}
          </div>

          {/* Footer — timestamp + status */}
          <div
            className={`mt-1.5 flex items-center gap-2 px-1 text-[11px] ${isUser ? "justify-end" : "justify-start"}`}
            style={{ color: theme.muted }}
          >
            <span>
              {message.timestamp.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
            </span>
            {!isUser && <span>·</span>}
            {!isUser && <span>Delivered</span>}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
