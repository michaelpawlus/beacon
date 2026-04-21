"use client";

import type { CSSProperties, ReactNode } from "react";
import type { Tokens } from "@/lib/tokens";

export function Kbd({ children, t }: { children: ReactNode; t: Tokens }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 18,
        height: 18,
        padding: "0 5px",
        fontFamily: t.fontMono,
        fontSize: 10.5,
        fontWeight: 500,
        color: t.textDim,
        background: t.panelAlt,
        border: `1px solid ${t.border}`,
        borderRadius: 4,
        lineHeight: 1,
      }}
    >
      {children}
    </span>
  );
}

export type PillTone = "default" | "accent" | "warn" | "bad" | "ghost";

export function Pill({
  children,
  t,
  tone = "default",
  mono = false,
}: {
  children: ReactNode;
  t: Tokens;
  tone?: PillTone;
  mono?: boolean;
}) {
  const tones: Record<PillTone, { bg: string; fg: string; bd: string }> = {
    default: { bg: t.panelAlt, fg: t.textDim, bd: t.border },
    accent: { bg: t.accentSoft, fg: t.accentInk, bd: "transparent" },
    warn: { bg: t.warnSoft, fg: t.warn, bd: "transparent" },
    bad: { bg: t.badSoft, fg: t.bad, bd: "transparent" },
    ghost: { bg: "transparent", fg: t.textDim, bd: t.border },
  };
  const s = tones[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "2px 7px",
        borderRadius: 4,
        fontFamily: mono ? t.fontMono : t.fontSans,
        fontSize: 11,
        fontWeight: 500,
        lineHeight: 1.4,
        background: s.bg,
        color: s.fg,
        border: `1px solid ${s.bd}`,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

export function MatchDot({ score, t, size = 22 }: { score: number; t: Tokens; size?: number }) {
  const tier = score >= 85 ? t.accent : score >= 70 ? t.warn : t.textMute;
  const r = size / 2 - 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - score / 100);
  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
      }}
    >
      <svg width={size} height={size} style={{ position: "absolute", transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={t.border} strokeWidth="2" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tier}
          strokeWidth="2"
          strokeDasharray={c}
          strokeDashoffset={off}
          strokeLinecap="round"
        />
      </svg>
      <span style={{ fontFamily: t.fontMono, fontSize: size * 0.34, fontWeight: 600, color: t.text, lineHeight: 1 }}>
        {score}
      </span>
    </span>
  );
}

export function Mono({
  name,
  t,
  size = 18,
  radius = 4,
}: {
  name: string;
  t: Tokens;
  size?: number;
  radius?: number;
}) {
  const letter = (name || "?").trim().charAt(0).toUpperCase();
  let h = 0;
  for (const ch of name || "") h = (h * 31 + ch.charCodeAt(0)) % 360;
  const isDark = t.bg === "#0b0b0c";
  const bg = `oklch(${isDark ? 0.36 : 0.86} 0.08 ${h})`;
  const fg = `oklch(${isDark ? 0.92 : 0.28} 0.06 ${h})`;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: radius,
        background: bg,
        color: fg,
        fontFamily: t.fontSans,
        fontSize: size * 0.5,
        fontWeight: 600,
        letterSpacing: -0.2,
        flexShrink: 0,
      }}
    >
      {letter}
    </span>
  );
}

export function Spark({
  points,
  t,
  w = 64,
  h = 18,
  color,
}: {
  points: number[];
  t: Tokens;
  w?: number;
  h?: number;
  color?: string;
}) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <path
        d={d}
        fill="none"
        stroke={color || t.accent}
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export type IconProps = { size?: number; color?: string; strokeWidth?: number; style?: CSSProperties };
