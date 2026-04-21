"use client";

import type { CSSProperties, ReactNode } from "react";
import type { Tokens } from "@/lib/tokens";
import type { BeaconData } from "@/lib/types";
import { Kbd, MatchDot, Mono, Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import { Topbar } from "@/components/chrome/topbar";

function Section({
  t,
  kicker,
  title,
  meta,
  children,
  compact,
  style,
}: {
  t: Tokens;
  kicker: string;
  title: string;
  meta?: string;
  children: ReactNode;
  compact?: boolean;
  style?: CSSProperties;
}) {
  return (
    <section style={{ ...style }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
          marginBottom: compact ? 6 : 18,
          borderBottom: compact ? "none" : `1px solid ${t.border}`,
          paddingBottom: compact ? 0 : 14,
        }}
      >
        <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute, letterSpacing: 1 }}>
          {kicker}
        </span>
        <span style={{ fontSize: 17, color: t.text, fontWeight: 500, letterSpacing: -0.3 }}>{title}</span>
        <div style={{ flex: 1 }} />
        {meta && <span style={{ fontSize: 12, color: t.textDim }}>{meta}</span>}
      </div>
      {children}
    </section>
  );
}

function actionBtn(t: Tokens, kind?: "primary"): CSSProperties {
  const primary = kind === "primary";
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "5px 10px",
    fontSize: 12,
    fontFamily: t.fontSans,
    fontWeight: 500,
    background: primary ? t.text : "transparent",
    color: primary ? t.bg : t.textDim,
    border: primary ? "1px solid transparent" : `1px solid ${t.border}`,
    borderRadius: 5,
    cursor: "pointer",
  };
}

export function DashB({ t, data }: { t: Tokens; data: BeaconData }) {
  const d = data;
  const today = new Date();
  const dateStr = today.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  return (
    <>
      <Topbar
        t={t}
        breadcrumbs={["Briefing"]}
        right={
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 10px",
              background: "transparent",
              border: `1px solid ${t.border}`,
              borderRadius: 5,
              color: t.textDim,
              fontSize: 12,
              fontFamily: t.fontSans,
              cursor: "pointer",
            }}
          >
            <icons.bolt size={11} />
            <span>Run sync</span>
            <Kbd t={t}>R</Kbd>
          </button>
        }
      />

      <div style={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center" }}>
        <div style={{ maxWidth: 960, width: "100%", padding: "40px 40px 80px" }}>
          <div style={{ marginBottom: 36 }}>
            <div
              style={{
                fontFamily: t.fontMono,
                fontSize: 11,
                letterSpacing: 1,
                color: t.textDim,
                textTransform: "uppercase",
              }}
            >
              Daily briefing · {dateStr}
            </div>
            <div
              style={{
                fontSize: 36,
                fontWeight: 500,
                color: t.text,
                letterSpacing: -1.2,
                lineHeight: 1.15,
                marginTop: 10,
                textWrap: "pretty" as CSSProperties["textWrap"],
              }}
            >
              You have{" "}
              <span style={{ color: t.accentInk }}>
                {d.newMatches.filter((m) => m.score >= 85).length} jobs worth looking at
              </span>
              , an onsite in 5 days, and one thread going cold.
            </div>
            <div
              style={{
                fontSize: 14,
                color: t.textDim,
                marginTop: 12,
                display: "flex",
                gap: 14,
                alignItems: "center",
              }}
            >
              <span>Synced 2m ago · 94 companies</span>
              <span style={{ width: 3, height: 3, borderRadius: 2, background: t.textMute }} />
              <span>{d.newMatches.length} new matches</span>
              <span style={{ width: 3, height: 3, borderRadius: 2, background: t.textMute }} />
              <span>{Math.round(d.stats.responseRate * 100)}% response rate this week</span>
            </div>
          </div>

          <Section t={t} kicker="01" title="Worth your time" meta={`3 of ${d.newMatches.length} new matches`}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {d.newMatches.slice(0, 3).map((j, i) => (
                <div
                  key={j.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "46px 1fr auto",
                    gap: 20,
                    padding: "20px 0",
                    borderTop: i > 0 ? `1px solid ${t.borderSoft}` : "none",
                  }}
                >
                  <div style={{ paddingTop: 2 }}>
                    <MatchDot score={j.score} t={t} size={34} />
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <Mono name={j.company} t={t} size={16} />
                      <span style={{ fontSize: 12.5, color: t.textDim, fontFamily: t.fontMono }}>
                        {j.company}
                      </span>
                      {j.referral && (
                        <Pill t={t} tone="accent">
                          <icons.sparkle size={10} /> warm intro
                        </Pill>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 20,
                        color: t.text,
                        fontWeight: 500,
                        letterSpacing: -0.4,
                        textWrap: "pretty" as CSSProperties["textWrap"],
                      }}
                    >
                      {j.title}
                    </div>
                    <div
                      style={{
                        fontSize: 13.5,
                        color: t.textDim,
                        marginTop: 8,
                        lineHeight: 1.55,
                        textWrap: "pretty" as CSSProperties["textWrap"],
                      }}
                    >
                      Matches on <span style={{ color: t.text }}>{j.stack.join(", ")}</span>. {j.loc}.{" "}
                      {j.seniority} level. Comp {j.comp}.
                    </div>
                    <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
                      <button style={actionBtn(t, "primary")}>
                        Apply <Kbd t={t}>A</Kbd>
                      </button>
                      <button style={actionBtn(t)}>Save for later</button>
                      <button style={actionBtn(t)}>Hide</button>
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
                      {j.posted} ago
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14, fontSize: 13, color: t.textDim }}>
              <span
                style={{
                  color: t.text,
                  borderBottom: `1px solid ${t.textDim}`,
                  paddingBottom: 1,
                }}
              >
                {Math.max(0, d.newMatches.length - 3)} more matches
              </span>{" "}
              scored above your threshold →
            </div>
          </Section>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40, marginTop: 48 }}>
            <Section t={t} kicker="02" title="On your calendar" compact>
              {d.interviews.map((iv, i) => (
                <div
                  key={i}
                  style={{ padding: "14px 0", borderTop: i > 0 ? `1px solid ${t.borderSoft}` : "none" }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <span
                      style={{
                        fontFamily: t.fontMono,
                        fontSize: 11,
                        color: t.accentInk,
                        letterSpacing: 0.5,
                        minWidth: 70,
                      }}
                    >
                      {iv.when}
                    </span>
                    <span style={{ fontSize: 14, color: t.text, fontWeight: 500 }}>{iv.company}</span>
                    <span style={{ fontSize: 13, color: t.textDim }}>· {iv.kind}</span>
                  </div>
                  <div style={{ fontSize: 12.5, color: t.textDim, marginTop: 4, marginLeft: 80 }}>
                    {iv.role} · {iv.who} ·{" "}
                    <span style={{ color: iv.prep >= 50 ? t.accentInk : t.warn }}>{iv.prep}% prep done</span>
                  </div>
                </div>
              ))}
            </Section>

            <Section t={t} kicker="03" title="Threads going cold" compact>
              {d.follow.map((f, i) => (
                <div
                  key={i}
                  style={{ padding: "14px 0", borderTop: i > 0 ? `1px solid ${t.borderSoft}` : "none" }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <span
                      style={{
                        fontFamily: t.fontMono,
                        fontSize: 11,
                        color: f.tone === "bad" ? t.bad : f.tone === "warn" ? t.warn : t.textDim,
                        minWidth: 36,
                      }}
                    >
                      {f.days}d
                    </span>
                    <span style={{ fontSize: 14, color: t.text, fontWeight: 500 }}>{f.who}</span>
                  </div>
                  <div style={{ fontSize: 12.5, color: t.textDim, marginTop: 4, marginLeft: 46 }}>
                    {f.action}
                  </div>
                </div>
              ))}
            </Section>
          </div>

          <Section t={t} kicker="04" title="From the watchlist" meta="Last 72h" style={{ marginTop: 48 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px" }}>
              {d.news.map((n, i) => (
                <div
                  key={i}
                  style={{
                    padding: "14px 0",
                    borderTop: i > 1 ? `1px solid ${t.borderSoft}` : "none",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                  }}
                >
                  <Mono name={n.company} t={t} size={20} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, color: t.text, fontWeight: 500 }}>
                      {n.company}{" "}
                      <span style={{ color: t.textMute, fontWeight: 400 }}>· {n.when}</span>
                    </div>
                    <div
                      style={{
                        fontSize: 13,
                        color: t.textDim,
                        marginTop: 3,
                        textWrap: "pretty" as CSSProperties["textWrap"],
                      }}
                    >
                      {n.text}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <div
            style={{
              marginTop: 56,
              padding: "16px 18px",
              border: `1px dashed ${t.border}`,
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontFamily: t.fontMono,
              fontSize: 11.5,
              color: t.textDim,
            }}
          >
            <span style={{ color: t.accent, display: "inline-flex" }}>
              <icons.terminal size={13} />
            </span>
            <span style={{ color: t.text }}>beacon pull --watchlist</span>
            <span>→ 94 companies · {d.newMatches.length} new · 1 rate-limited</span>
            <div style={{ flex: 1 }} />
            <span>14:02:11</span>
            <Kbd t={t}>⌘R</Kbd>
          </div>
        </div>
      </div>
    </>
  );
}
