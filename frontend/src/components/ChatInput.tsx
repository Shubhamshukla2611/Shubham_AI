import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useVoiceTyping } from "@/hooks/useVoiceTyping";

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

interface ChatInputProps {
  onSubmit: (message: string) => void;
  disabled: boolean;
  placeholder?: string;
  theme: ChatTheme;
  onBookCall?: () => void;
}

// How long the transcript must stay unchanged (no new final or interim
// chunks) before we treat the user as having stopped speaking, stop the mic,
// and auto-send the message.
const AUTO_SEND_SILENCE_MS = 1000;

export function ChatInput({ onSubmit, disabled, placeholder, theme, onBookCall }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [message, setMessage] = useState("");

  // Snapshot of the textarea contents captured the moment a new speech
  // session starts. The recognized transcript is appended after this base.
  const baseTextRef = useRef<string>("");
  // Latest message value, mirrored into a ref so the recognition callback
  // (which closes over an old value) can see the current one.
  const messageRef = useRef<string>(message);
  useEffect(() => {
    messageRef.current = message;
  }, [message]);

  // Latest transcript text (recognized portion only — not the full message),
  // used to detect when the user has stopped producing new text.
  const lastTranscriptRef = useRef<string>("");
  // Auto-send timer and a flag distinguishing "user manually toggled the mic
  // off" (don't auto-send) from "user went silent" (auto-send).
  const autoSendTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualStopRef = useRef<boolean>(false);
  // Disabled while a send is in flight (the parent toggles `disabled` to true
  // until the response lands); we still want to call submit() once when the
  // timer fires, so we cache the latest message at fire time.
  const disabledRef = useRef<boolean>(disabled);
  useEffect(() => {
    disabledRef.current = disabled;
  }, [disabled]);

  const clearAutoSendTimer = useCallback(() => {
    if (autoSendTimerRef.current != null) {
      clearTimeout(autoSendTimerRef.current);
      autoSendTimerRef.current = null;
    }
  }, []);

  const { isSupported, isListening, error: voiceError, toggle, stop } = useVoiceTyping({
    onResult: (transcript) => {
      // Splice the recognized transcript after whatever the user had typed
      // when the session started.
      const base = baseTextRef.current;
      const sep = base && !base.endsWith(" ") && !transcript.startsWith(" ") ? " " : "";
      setMessage(base + sep + transcript);

      // Reset the auto-send timer. The next event (interim or final) bumps
      // it again; when the user goes silent for AUTO_SEND_SILENCE_MS, we
      // stop the mic and submit.
      lastTranscriptRef.current = transcript;
      if (autoSendTimerRef.current != null) clearTimeout(autoSendTimerRef.current);
      autoSendTimerRef.current = setTimeout(() => {
        autoSendTimerRef.current = null;
        // Only auto-send if the user didn't manually stop the mic.
        if (manualStopRef.current) return;
        stop();
        // The recognition `onend` will flip isListening false, but in case
        // it doesn't, also no-op the manualStopRef on the next session.
        const final = messageRef.current.trim();
        if (!final || disabledRef.current) return;
        // Use the same path as the form submit.
        onSubmitInternal(final);
      }, AUTO_SEND_SILENCE_MS);
    },
  });

  // The internal submit, used by the auto-send path and the regular
  // form-submit. Centralized so the two paths stay in sync.
  const onSubmitInternal = useCallback(
    (text: string) => {
      onSubmit(text);
      setMessage("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    },
    [onSubmit]
  );

  // When listening starts, snapshot the current message as the base, reset
  // the transcript tracker, and clear any manual-stop flag.
  useEffect(() => {
    if (isListening) {
      baseTextRef.current = messageRef.current;
      lastTranscriptRef.current = "";
      manualStopRef.current = false;
    } else {
      baseTextRef.current = "";
      // Listening stopped — clear any pending auto-send. The submit either
      // already fired (silence path) or will not fire (manual toggle path).
      clearAutoSendTimer();
    }
  }, [isListening, clearAutoSendTimer]);

  // Wrap the hook's `toggle` so we can mark "user manually stopped" — that
  // way the in-flight auto-send timer becomes a no-op.
  const handleToggleMic = useCallback(() => {
    if (isListening) {
      manualStopRef.current = true;
      clearAutoSendTimer();
    }
    toggle();
  }, [isListening, toggle, clearAutoSendTimer]);

  // Cleanup the timer on unmount.
  useEffect(() => {
    return () => clearAutoSendTimer();
  }, [clearAutoSendTimer]);

  // Auto-resize the textarea to fit the text. Cap at ~6 lines so the input
  // row doesn't dominate the screen during long dictation, and always keep
  // a minimum height so an empty textarea stays visible.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 64), 180)}px`;
  }, [message]);

  const submit = () => {
    const next = message.trim();
    if (!next || disabled) return;
    // Stop the mic before sending so it doesn't keep streaming into a
    // cleared textarea.
    if (isListening) {
      manualStopRef.current = true;
      clearAutoSendTimer();
      stop();
    }
    onSubmitInternal(next);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    const target = e.currentTarget;
    target.style.height = "auto";
    target.style.height = `${Math.min(Math.max(target.scrollHeight, 64), 180)}px`;
  };

  const sendButton = (
    <motion.button
      type="submit"
      whileHover={{ scale: 1.03, y: -1 }}
      whileTap={{ scale: 0.95 }}
      disabled={disabled}
      className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white shadow-[0_16px_36px_rgba(109,93,252,0.26)] transition-all disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: `linear-gradient(135deg, ${theme.accent} 0%, ${theme.accentTwo} 100%)` }}
    >
      {disabled ? (
        <svg className="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="10" opacity="0.25" />
          <path d="M22 12a10 10 0 00-10-10" />
        </svg>
      ) : (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
      )}
    </motion.button>
  );

  // Mic button matches the send button's gradient and sizing for visual
  // consistency. While listening, the icon swaps to a stop glyph and a
  // pulsing recording ring is layered on top.
  const micGradient = `linear-gradient(135deg, ${theme.accent} 0%, ${theme.accentTwo} 100%)`;

  const micButton = (
    <motion.button
      type="button"
      onClick={handleToggleMic}
      disabled={disabled || !isSupported}
      aria-label={isListening ? "Stop voice typing" : "Start voice typing"}
      aria-pressed={isListening}
      title={
        !isSupported
          ? "Voice typing is not supported in this browser"
          : isListening
            ? "Tap to stop"
            : "Tap to dictate"
      }
      whileHover={isSupported ? { scale: 1.03, y: -1 } : undefined}
      whileTap={isSupported ? { scale: 0.95 } : undefined}
      className="relative inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white shadow-[0_16px_36px_rgba(109,93,252,0.26)] transition-all disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: micGradient }}
    >
      {isListening && (
        <span
          className="vt-pulse-ring pointer-events-none absolute -inset-1 rounded-full"
          aria-hidden
          style={{ color: theme.accent }}
        />
      )}
      {isListening ? (
        // Stop icon — a rounded square (white on the gradient).
        <svg className="relative h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <rect x="6" y="6" width="12" height="12" rx="3" />
        </svg>
      ) : (
        // Mic icon.
        <svg
          className="relative h-6 w-6"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M12 2a3 3 0 00-3 3v6a3 3 0 006 0V5a3 3 0 00-3-3z" />
          <path d="M19 11a7 7 0 01-14 0" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="8" y1="22" x2="16" y2="22" />
        </svg>
      )}
    </motion.button>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={message}
          placeholder={placeholder || "Ask me anything…"}
          disabled={disabled}
          onKeyDown={handleKeyDown}
          onChange={handleChange}
          rows={1}
          className="min-h-[64px] w-full resize-none rounded-[24px] border px-5 py-3.5 text-[15px] leading-7 outline-none transition-all duration-200 focus:ring-2 focus:ring-offset-0"
          style={{
            background: theme.inputBg,
            borderColor: isListening ? `${theme.accent}66` : `${theme.accent}18`,
            color: theme.text,
            boxShadow: isListening
              ? `0 0 0 4px ${theme.accent}1a, ${theme.insetShadow}`
              : `${theme.insetShadow}, inset 0 0 0 1px ${theme.accent}08`,
            overflow: "auto",
          }}
        />

        {micButton}
        {onBookCall && (
          <motion.button
            type="button"
            onClick={onBookCall}
            disabled={disabled}
            whileHover={{ scale: 1.03, y: -1 }}
            whileTap={{ scale: 0.95 }}
            title="Book a call with Shubham"
            className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white shadow-[0_16px_36px_rgba(109,93,252,0.26)] transition-all disabled:cursor-not-allowed disabled:opacity-60"
            style={{ background: `linear-gradient(135deg, ${theme.accent} 0%, ${theme.accentTwo} 100%)` }}
          >
            <span className="text-xl">📞</span>
          </motion.button>
        )}
        {sendButton}
      </div>

      {isListening && !voiceError && (
        <div
          className="flex items-center gap-2 px-2 text-[11px] font-medium"
          aria-live="polite"
          style={{ color: theme.muted }}
        >
          <span
            className="vt-listening-dot inline-block h-2 w-2 rounded-full"
            style={{ background: theme.accent }}
          />
          Listening… auto-sends 1s after you stop speaking
        </div>
      )}

      {voiceError && (
        <div
          className="rounded-full border px-3 py-1.5 text-xs"
          role="alert"
          style={{
            background: "rgba(248,113,113,0.10)",
            borderColor: "rgba(248,113,113,0.28)",
            color: "#b91c1c",
          }}
        >
          {voiceError}
        </div>
      )}

      <style>{`
        @keyframes vt-pulse {
          0% { box-shadow: 0 0 0 0 currentColor; opacity: 0.7; }
          70% { box-shadow: 0 0 0 14px transparent; opacity: 0; }
          100% { box-shadow: 0 0 0 0 transparent; opacity: 0; }
        }
        .vt-pulse-ring { animation: vt-pulse 1.6s ease-out infinite; }
        @keyframes vt-blink {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.85); }
        }
        .vt-listening-dot { animation: vt-blink 1s ease-in-out infinite; }
      `}</style>
    </form>
  );
}
