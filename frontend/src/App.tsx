import { useEffect, useState } from "react";
import { ChatContainer } from "./components/ChatContainer";

type ThemeName = "light" | "dark" | "purple";

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

const THEMES: Record<ThemeName, ChatTheme> = {
  light: {
    name: "light",
    label: "Light Clay",
    background: "linear-gradient(180deg, #f8f7ff 0%, #f3f5ff 50%, #eef2ff 100%)",
    shell: "rgba(255,255,255,0.82)",
    shellBorder: "rgba(255,255,255,0.72)",
    shellShadow: "12px 12px 24px rgba(163,177,198,0.22), -12px -12px 24px rgba(255,255,255,0.9)",
    card: "rgba(248,250,255,0.95)",
    cardBorder: "rgba(129,140,248,0.16)",
    cardShadow: "12px 12px 24px rgba(163,177,198,0.18), -10px -10px 20px rgba(255,255,255,0.7)",
    insetShadow: "inset 6px 6px 16px rgba(15,23,42,0.06), inset -6px -6px 16px rgba(255,255,255,0.9)",
    text: "#111827",
    muted: "#64748b",
    accent: "#7c5cff",
    accentSoft: "rgba(124,92,255,0.12)",
    accentTwo: "#9c89ff",
    inputBg: "rgba(244,246,255,0.95)",
    assistantBg: "rgba(255,255,255,0.94)",
    assistantText: "#111827",
    userBg: "linear-gradient(135deg, #7c5cff 0%, #9c89ff 100%)",
    userText: "#ffffff",
    online: "#22c55e",
    blobA: "rgba(124,92,255,0.16)",
    blobB: "rgba(255,255,255,0.85)",
  },
  dark: {
    name: "dark",
    label: "Dark Clay",
    background: "linear-gradient(180deg, #121723 0%, #151c2c 50%, #1a2131 100%)",
    shell: "rgba(29,34,51,0.92)",
    shellBorder: "rgba(255,255,255,0.08)",
    shellShadow: "14px 14px 36px rgba(2,6,23,0.4), -12px -12px 28px rgba(255,255,255,0.03)",
    card: "rgba(39,46,66,0.95)",
    cardBorder: "rgba(255,255,255,0.08)",
    cardShadow: "12px 12px 24px rgba(2,6,23,0.35), -8px -8px 18px rgba(255,255,255,0.03)",
    insetShadow: "inset 6px 6px 16px rgba(2,6,23,0.28), inset -6px -6px 16px rgba(255,255,255,0.02)",
    text: "#f8fafc",
    muted: "#94a3b8",
    accent: "#8b7cff",
    accentSoft: "rgba(139,124,255,0.18)",
    accentTwo: "#b8aaff",
    inputBg: "rgba(29,34,51,0.95)",
    assistantBg: "rgba(34,41,61,0.96)",
    assistantText: "#f8fafc",
    userBg: "linear-gradient(135deg, #8b7cff 0%, #b8aaff 100%)",
    userText: "#ffffff",
    online: "#4ade80",
    blobA: "rgba(139,124,255,0.16)",
    blobB: "rgba(15,23,42,0.65)",
  },
  purple: {
    name: "purple",
    label: "Purple AI",
    background: "linear-gradient(135deg, #f7f1ff 0%, #efe9ff 45%, #e9f0ff 100%)",
    shell: "rgba(255,255,255,0.8)",
    shellBorder: "rgba(124,92,255,0.18)",
    shellShadow: "16px 16px 32px rgba(137,106,255,0.16), -12px -12px 24px rgba(255,255,255,0.86)",
    card: "rgba(255,255,255,0.9)",
    cardBorder: "rgba(124,92,255,0.16)",
    cardShadow: "12px 12px 24px rgba(139,92,246,0.14), -10px -10px 20px rgba(255,255,255,0.8)",
    insetShadow: "inset 6px 6px 16px rgba(124,92,255,0.08), inset -6px -6px 16px rgba(255,255,255,0.92)",
    text: "#24163d",
    muted: "#7c6aa9",
    accent: "#6d4ff2",
    accentSoft: "rgba(109,79,242,0.12)",
    accentTwo: "#9b7dff",
    inputBg: "rgba(248,244,255,0.98)",
    assistantBg: "rgba(255,255,255,0.94)",
    assistantText: "#24163d",
    userBg: "linear-gradient(135deg, #6d4ff2 0%, #9b7dff 100%)",
    userText: "#ffffff",
    online: "#22c55e",
    blobA: "rgba(109,79,242,0.2)",
    blobB: "rgba(255,255,255,0.9)",
  },
};

function App() {
  const [themeName, setThemeName] = useState<ThemeName>(() => {
    if (typeof window === "undefined") {
      return "light";
    }
    return (localStorage.getItem("theme") as ThemeName) || "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", themeName !== "light");
    root.setAttribute("data-theme", themeName);
    root.style.colorScheme = themeName === "dark" ? "dark" : "light";
    localStorage.setItem("theme", themeName);
  }, [themeName]);

  const theme = THEMES[themeName];

  return (
    <div
      className="relative min-h-[100dvh] overflow-hidden px-2 py-0 text-slate-900 sm:px-4 sm:py-4 lg:px-6 lg:py-6"
      style={{ background: theme.background }}
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute left-[-8%] top-[-6%] h-56 w-56 rounded-full blur-3xl"
          style={{ background: theme.blobA }}
        />
        <div
          className="absolute bottom-[-5%] right-[-4%] h-64 w-64 rounded-full blur-3xl"
          style={{ background: theme.blobB }}
        />
      </div>

      <div className="relative mx-auto flex min-h-[calc(100dvh-0.5rem)] max-w-6xl items-stretch justify-center sm:min-h-[calc(100dvh-2rem)] sm:items-center sm:justify-center">
        <div className="w-full max-w-[560px]">
          <ChatContainer theme={theme} onThemeChange={setThemeName} />
        </div>
      </div>
    </div>
  );
}

export default App;