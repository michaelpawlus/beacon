"use client";

import type { Tokens } from "@/lib/tokens";
import { Kbd, MatchDot, Mono, Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import type { JobMatch } from "@/lib/types";

export type JobCardVariant = "row" | "stacked" | "brief" | "terminal";

export function JobCardSwatch({
  variant,
  t,
  job,
}: {
  variant: JobCardVariant;
  t: Tokens;
  job: JobMatch;
}) {
  const j = job;
  const frame = (inner: React.ReactNode) => (
    <div
      style={{
        background: t.bg,
        padding: 16,
        height: "100%",
        boxSizing: "border-box",
        fontFamily: t.fontSans,
        color: t.text,
      }}
    >
      {inner}
    </div>
  );

  if (variant === "row") {
    return frame(
      <div
        style={{
          background: t.panel,
          border: `1px solid ${t.border}`,
          borderRadius: 6,
          padding: "12px 14px",
          display: "grid",
          gridTemplateColumns: "28px 1fr auto",
          gap: 12,
          alignItems: "center",
        }}
      >
        <MatchDot score={j.score} t={t} />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Mono name={j.company} t={t} size={14} radius={3} />
            <span style={{ fontSize: 13, fontWeight: 500 }}>{j.title}</span>
            {j.referral && (
              <span style={{ color: t.accent, display: "inline-flex" }}>
                <icons.sparkle size={11} />
              </span>
            )}
          </div>
          <div style={{ fontSize: 11.5, color: t.textDim, marginTop: 3 }}>
            {j.company} · {j.loc} · {j.comp}
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {j.stack.slice(0, 2).map((s) => (
            <Pill key={s} t={t} mono>
              {s}
            </Pill>
          ))}
        </div>
      </div>,
    );
  }

  if (variant === "stacked") {
    return frame(
      <div style={{ background: t.panel, border: `1px solid ${t.border}`, borderRadius: 8, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <Mono name={j.company} t={t} size={28} radius={6} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: t.textDim }}>{j.company}</div>
            <div
              style={{
                fontSize: 10.5,
                color: t.textMute,
                fontFamily: t.fontMono,
                letterSpacing: 0.4,
                textTransform: "uppercase",
                marginTop: 2,
              }}
            >
              {j.posted} ago · {j.loc}
            </div>
          </div>
          <MatchDot score={j.score} t={t} size={32} />
        </div>
        <div style={{ fontSize: 16, fontWeight: 500, letterSpacing: -0.2, marginBottom: 10 }}>
          {j.title}
        </div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 14 }}>
          {j.stack.map((s) => (
            <Pill key={s} t={t} mono>
              {s}
            </Pill>
          ))}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingTop: 12,
            borderTop: `1px solid ${t.borderSoft}`,
          }}
        >
          <span style={{ fontFamily: t.fontMono, fontSize: 11.5, color: t.textDim }}>{j.comp}</span>
          {j.referral && (
            <Pill t={t} tone="accent">
              <icons.sparkle size={10} /> warm intro
            </Pill>
          )}
        </div>
      </div>,
    );
  }

  if (variant === "brief") {
    return frame(
      <div style={{ padding: "8px 2px" }}>
        <div style={{ fontFamily: t.fontMono, fontSize: 10, color: t.accentInk, letterSpacing: 1 }}>
          MATCH · {j.score}
        </div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 500,
            letterSpacing: -0.5,
            marginTop: 8,
            textWrap: "pretty" as React.CSSProperties["textWrap"],
          }}
        >
          {j.title}
        </div>
        <div
          style={{
            fontSize: 13,
            color: t.textDim,
            marginTop: 6,
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <Mono name={j.company} t={t} size={14} />
          {j.company} · {j.loc}
        </div>
        <div style={{ fontSize: 13, color: t.textDim, marginTop: 12, lineHeight: 1.55 }}>
          Matches on <span style={{ color: t.text }}>{j.stack.join(", ")}</span>. {j.comp}. Warm intro via
          B. Ho.
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
          <button
            style={{
              padding: "5px 10px",
              fontSize: 12,
              background: t.text,
              color: t.bg,
              border: "none",
              borderRadius: 5,
              fontFamily: t.fontSans,
              fontWeight: 500,
            }}
          >
            Apply
          </button>
          <button
            style={{
              padding: "5px 10px",
              fontSize: 12,
              background: "transparent",
              color: t.textDim,
              border: `1px solid ${t.border}`,
              borderRadius: 5,
              fontFamily: t.fontSans,
            }}
          >
            Save
          </button>
        </div>
      </div>,
    );
  }

  return frame(
    <div
      style={{
        border: `1px solid ${t.border}`,
        borderRadius: 4,
        background: t.panel,
        padding: 12,
        fontFamily: t.fontMono,
        fontSize: 11.5,
        lineHeight: 1.7,
      }}
    >
      <div style={{ color: t.textMute }}>
        ─ job:{j.id} ─ score:<span style={{ color: t.accentInk }}>{j.score}</span> ─────────
      </div>
      <div>
        <span style={{ color: t.textMute }}>co   </span>
        {j.company.toLowerCase()}
      </div>
      <div>
        <span style={{ color: t.textMute }}>role </span>
        <span style={{ color: t.text }}>{j.title}</span>
      </div>
      <div>
        <span style={{ color: t.textMute }}>loc  </span>
        {j.loc}
      </div>
      <div>
        <span style={{ color: t.textMute }}>comp </span>
        {j.comp}
      </div>
      <div>
        <span style={{ color: t.textMute }}>stack</span>[{j.stack.map((s) => s.toLowerCase()).join(", ")}]
      </div>
      {j.referral && (
        <div>
          <span style={{ color: t.textMute }}>ref  </span>
          <span style={{ color: t.accent }}>✓ warm intro</span>
        </div>
      )}
      <div style={{ color: t.textMute, marginTop: 6 }}>
        ─ <Kbd t={t}>a</Kbd> apply · <Kbd t={t}>s</Kbd> save ─
      </div>
    </div>,
  );
}
