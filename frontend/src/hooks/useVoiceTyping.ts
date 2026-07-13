import { useEffect, useRef, useState } from "react";

// Browser Speech Recognition isn't in the standard TS lib types, so we
// declare the minimal surface we use.
interface SpeechRecognitionResultLike {
  readonly transcript: string;
  readonly isFinal: boolean;
}

interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number;
  readonly results: ArrayLike<{
    readonly transcript: string;
    readonly isFinal: boolean;
    readonly length: number;
    [index: number]: SpeechRecognitionResultLike;
  }>;
}

interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
  readonly message?: string;
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((this: SpeechRecognitionLike, ev: SpeechRecognitionEventLike) => void) | null;
  onerror: ((this: SpeechRecognitionLike, ev: SpeechRecognitionErrorEventLike) => void) | null;
  onend: ((this: SpeechRecognitionLike, ev: Event) => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

const getSpeechRecognitionCtor = (): SpeechRecognitionCtor | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

export interface UseVoiceTypingOptions {
  /**
   * Called whenever new transcript is available.
   * `text` is the *cumulative* transcript for the current session — every
   * finalized chunk so far, plus the latest interim tail if `isFinal` is false.
   * `isFinal` indicates whether the latest chunk is a finalized result.
   */
  onResult: (text: string, isFinal: boolean) => void;
  lang?: string;
}

export interface UseVoiceTypingReturn {
  isSupported: boolean;
  isListening: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
  toggle: () => void;
}

/**
 * Wraps the browser's Web Speech API so the parent component can stream
 * recognized text into a textarea as the user speaks.
 *
 * The hook owns the recognition instance and emits a cumulative session
 * transcript on every `result` event. The parent decides how to splice that
 * into its own state (see ChatInput for one approach).
 *
 * - `continuous: true` and `interimResults: true` are set so words stream in
 *   live ("typing while I speak").
 * - On `error` or `end`, listening state resets to false. The browser auto-ends
 *   after a silence window; the user can simply toggle to resume.
 * - On `start()` the session transcript resets to "".
 */
export function useVoiceTyping({ onResult, lang }: UseVoiceTypingOptions): UseVoiceTypingReturn {
  const CtorRef = useRef<SpeechRecognitionCtor | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const sessionTextRef = useRef<string>("");
  // Captured by ref so the recognition event handlers always see the latest
  // callback without us having to rebuild the recognition instance.
  const onResultRef = useRef(onResult);
  useEffect(() => {
    onResultRef.current = onResult;
  });

  const [isSupported] = useState<boolean>(() => getSpeechRecognitionCtor() != null);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const ensureInstance = (): SpeechRecognitionLike | null => {
    if (recognitionRef.current) return recognitionRef.current;
    const Ctor = CtorRef.current ?? getSpeechRecognitionCtor();
    if (!Ctor) return null;
    CtorRef.current = Ctor;
    const instance = new Ctor();
    instance.continuous = true;
    instance.interimResults = true;
    instance.lang = lang || (typeof navigator !== "undefined" ? navigator.language : "en-US") || "en-US";

    instance.onresult = (event) => {
      let finalDelta = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalDelta += transcript;
        } else {
          interim = transcript;
        }
      }
      if (finalDelta) {
        sessionTextRef.current = joinWithSpace(sessionTextRef.current, finalDelta);
      }
      const cumulative = joinWithSpace(sessionTextRef.current, interim);
      const isFinal = Boolean(finalDelta);
      onResultRef.current(cumulative, isFinal);
    };

    instance.onerror = (event) => {
      const code = event.error || "unknown";
      setError(humanizeError(code));
      setIsListening(false);
    };

    instance.onend = () => {
      // Browser auto-ends after silence; just reflect state.
      setIsListening(false);
    };

    recognitionRef.current = instance;
    return instance;
  };

  const start = () => {
    if (!CtorRef.current) CtorRef.current = getSpeechRecognitionCtor();
    if (!CtorRef.current) {
      setError("Voice typing is not supported in this browser.");
      return;
    }
    setError(null);
    // Reset session accumulation for a new listening session.
    sessionTextRef.current = "";
    const instance = ensureInstance();
    if (!instance) return;
    try {
      instance.start();
      setIsListening(true);
    } catch (err) {
      if (err instanceof Error) setError(err.message);
      setIsListening(true);
    }
  };

  const stop = () => {
    const instance = recognitionRef.current;
    if (!instance) {
      setIsListening(false);
      return;
    }
    try {
      instance.stop();
    } catch {
      // Some browsers throw if recognition isn't started; ignore.
    }
    setIsListening(false);
  };

  const toggle = () => {
    if (isListening) stop();
    else start();
  };

  useEffect(() => {
    return () => {
      // Abort on unmount to release the mic promptly.
      const instance = recognitionRef.current;
      if (instance) {
        try {
          instance.onresult = null;
          instance.onerror = null;
          instance.onend = null;
          instance.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  return { isSupported, isListening, error, start, stop, toggle };
}

function joinWithSpace(a: string, b: string): string {
  if (!a) return b;
  if (!b) return a;
  const sep = a.endsWith(" ") || b.startsWith(" ") ? "" : " ";
  return `${a}${sep}${b}`;
}

function humanizeError(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access was denied. Allow mic permission and try again.";
    case "no-speech":
      return "No speech detected. Try again.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
      return "Network error. Voice typing needs an internet connection.";
    case "aborted":
      // Aborted by us — not really an error worth showing.
      return "";
    default:
      return `Voice typing error: ${code}`;
  }
}
