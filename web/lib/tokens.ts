export type Theme = "dark" | "light";

export type Tokens = {
  bg: string;
  panel: string;
  panelAlt: string;
  hover: string;
  border: string;
  borderSoft: string;
  text: string;
  textDim: string;
  textMute: string;
  accent: string;
  accentSoft: string;
  accentInk: string;
  warn: string;
  warnSoft: string;
  bad: string;
  badSoft: string;
  fontSans: string;
  fontMono: string;
};

export function beaconTokens(theme: Theme = "dark"): Tokens {
  const dark = theme === "dark";
  return {
    bg: dark ? "#0b0b0c" : "#fbfaf7",
    panel: dark ? "#121214" : "#ffffff",
    panelAlt: dark ? "#17171a" : "#f4f2ed",
    hover: dark ? "#1c1c20" : "#ececea",
    border: dark ? "#23232a" : "#e8e5df",
    borderSoft: dark ? "#1a1a1e" : "#ededea",
    text: dark ? "#ededee" : "#1a1a1c",
    textDim: dark ? "#9a9aa2" : "#60605e",
    textMute: dark ? "#6a6a72" : "#8b8b86",
    accent: "oklch(0.74 0.17 145)",
    accentSoft: dark ? "oklch(0.74 0.17 145 / 0.14)" : "oklch(0.74 0.17 145 / 0.18)",
    accentInk: dark ? "oklch(0.82 0.17 145)" : "oklch(0.42 0.13 145)",
    warn: "oklch(0.78 0.14 75)",
    warnSoft: dark ? "oklch(0.78 0.14 75 / 0.14)" : "oklch(0.78 0.14 75 / 0.2)",
    bad: "oklch(0.66 0.18 25)",
    badSoft: dark ? "oklch(0.66 0.18 25 / 0.14)" : "oklch(0.66 0.18 25 / 0.18)",
    fontSans:
      'var(--font-geist-sans), "Geist", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
    fontMono:
      'var(--font-geist-mono), "Geist Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
  };
}
