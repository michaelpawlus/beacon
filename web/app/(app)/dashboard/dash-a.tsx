"use client";

import type { Tokens } from "@/lib/tokens";
import type { BeaconData } from "@/lib/types";
import { Kbd, MatchDot, Mono, Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import { Topbar } from "@/components/chrome/topbar";

export function DashA({ t, data }: { t: Tokens; data: BeaconData }) {
  const d = data;
  return (
    <>
      <Topbar
        t={t}
        breadcrumbs={["Dashboard"]}
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Pill t={t} tone="ghost">
              <span style={{ width: 5, height: 5, borderRadius: 3, background: t.accent }} />
              CLI · 2m ago
            </Pill>
            <button
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 10px",
                background: t.panelAlt,
                border: `1px solid ${t.border}`,
                borderRadius: 5,
                color: t.text,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              <icons.bolt size={11} />
              <span>Run sync</span>
            </button>
          </div>
        }
      />

      <div style={{ flex: 1, overflow: "auto", padding: "22px 28px 40px" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 16, marginBottom: 22 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 600, color: t.text, letterSpacing: -0.5 }}>
              Good morning, Michael.
            </div>
            <div style={{ fontSize: 13, color: t.textDim, marginTop: 3 }}>
              {d.newMatches.length} new matches overnight · {d.interviews.length} upcoming interviews ·{" "}
              {d.follow.length} things need follow-up
            </div>
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ display: "flex", gap: 8 }}>
            {["Today", "This week", "All"].map((l, i) => (
              <span
                key={l}
                style={{
                  fontSize: 12,
                  padding: "4px 9px",
                  borderRadius: 5,
                  color: i === 0 ? t.text : t.textDim,
                  background: i === 0 ? t.panelAlt : "transparent",
                  border: i === 0 ? `1px solid ${t.border}` : "1px solid transparent",
                }}
              >
                {l}
              </span>
            ))}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 1,
            background: t.border,
            border: `1px solid ${t.border}`,
            borderRadius: 6,
            overflow: "hidden",
            marginBottom: 22,
          }}
        >
          {(
            [
              { k: "New matches", v: d.newMatches.length, delta: "+4", tone: "accent" },
              { k: "Applied · wk", v: d.stats.applied, delta: "+3", tone: "default" },
              { k: "Response rate", v: `${Math.round(d.stats.responseRate * 100)}%`, delta: "+6", tone: "accent" },
              { k: "Interviews", v: d.stats.interviews, delta: "+1", tone: "default" },
              { k: "Ghosted", v: d.pipeline.filter((p) => p.ghost).length, delta: "-1", tone: "warn" },
            ] as const
          ).map((s) => (
            <div key={s.k} style={{ background: t.panel, padding: "12px 14px" }}>
              <div
                style={{
                  fontSize: 11,
                  color: t.textDim,
                  marginBottom: 6,
                  textTransform: "uppercase",
                  letterSpacing: 0.4,
                }}
              >
                {s.k}
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <div
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 22,
                    fontWeight: 500,
                    color: t.text,
                    letterSpacing: -0.8,
                  }}
                >
                  {s.v}
                </div>
                <div
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 11,
                    color:
                      s.tone === "accent" ? t.accentInk : s.tone === "warn" ? t.warn : t.textDim,
                  }}
                >
                  {s.delta}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 20 }}>
          <div
            style={{
              background: t.panel,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "11px 14px",
                borderBottom: `1px solid ${t.borderSoft}`,
              }}
            >
              <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>New matches</span>
              <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute, marginLeft: 8 }}>
                · today
              </span>
              <div style={{ flex: 1 }} />
              <div style={{ display: "flex", gap: 4, color: t.textDim, alignItems: "center" }}>
                <icons.filter size={13} />
                <span style={{ fontSize: 11.5 }}>85+ score</span>
              </div>
            </div>
            {d.newMatches.slice(0, 6).map((j, i) => (
              <div
                key={j.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "28px 1.2fr 1fr auto auto",
                  gap: 12,
                  alignItems: "center",
                  padding: "10px 14px",
                  borderBottom: i < 5 ? `1px solid ${t.borderSoft}` : "none",
                }}
              >
                <MatchDot score={j.score} t={t} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <Mono name={j.company} t={t} size={14} radius={3} />
                    <span style={{ fontSize: 12.5, color: t.text, fontWeight: 500 }}>{j.title}</span>
                    {j.referral && (
                      <span title="Warm intro available" style={{ color: t.accent, display: "inline-flex" }}>
                        <icons.sparkle size={11} />
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11.5, color: t.textDim, marginTop: 2 }}>
                    {j.company} · {j.loc} · {j.seniority}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {j.stack.slice(0, 3).map((s) => (
                    <Pill key={s} t={t} mono>
                      {s}
                    </Pill>
                  ))}
                </div>
                <span
                  style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textDim, textAlign: "right" }}
                >
                  {j.comp}
                </span>
                <span
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 10.5,
                    color: t.textMute,
                    width: 28,
                    textAlign: "right",
                  }}
                >
                  {j.posted}
                </span>
              </div>
            ))}
            <div
              style={{
                padding: "9px 14px",
                display: "flex",
                alignItems: "center",
                gap: 8,
                color: t.textDim,
                fontSize: 11.5,
                borderTop: `1px solid ${t.borderSoft}`,
              }}
            >
              <Kbd t={t}>J</Kbd>
              <Kbd t={t}>K</Kbd>
              <span>navigate</span>
              <Kbd t={t}>A</Kbd>
              <span>apply</span>
              <Kbd t={t}>S</Kbd>
              <span>save</span>
              <Kbd t={t}>X</Kbd>
              <span>hide</span>
              <div style={{ flex: 1 }} />
              <span>View all {d.newMatches.length} →</span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div
              style={{
                background: t.panel,
                border: `1px solid ${t.border}`,
                borderRadius: 6,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  padding: "11px 14px",
                  borderBottom: `1px solid ${t.borderSoft}`,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>Upcoming interviews</span>
                <div style={{ flex: 1 }} />
                <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
                  {d.interviews.length}
                </span>
              </div>
              {d.interviews.map((iv, i) => {
                const parts = iv.when.split(" · ");
                return (
                  <div
                    key={i}
                    style={{
                      padding: "10px 14px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      borderBottom: i < d.interviews.length - 1 ? `1px solid ${t.borderSoft}` : "none",
                    }}
                  >
                    <div style={{ width: 44, textAlign: "center" }}>
                      <div style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textDim, lineHeight: 1 }}>
                        {parts[0]}
                      </div>
                      <div
                        style={{
                          fontFamily: t.fontMono,
                          fontSize: 13,
                          color: t.text,
                          fontWeight: 500,
                          marginTop: 3,
                        }}
                      >
                        {parts[1] || "—"}
                      </div>
                    </div>
                    <div style={{ width: 1, alignSelf: "stretch", background: t.borderSoft }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, color: t.text, fontWeight: 500 }}>
                        {iv.company}{" "}
                        <span style={{ color: t.textDim, fontWeight: 400 }}>· {iv.role}</span>
                      </div>
                      <div style={{ fontSize: 11.5, color: t.textDim, marginTop: 2 }}>
                        {iv.kind} · {iv.who}
                      </div>
                    </div>
                    <Pill t={t} tone={iv.prep >= 50 ? "accent" : iv.prep >= 25 ? "warn" : "bad"} mono>
                      {iv.prep}% prep
                    </Pill>
                  </div>
                );
              })}
            </div>

            <div
              style={{
                background: t.panel,
                border: `1px solid ${t.border}`,
                borderRadius: 6,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  padding: "11px 14px",
                  borderBottom: `1px solid ${t.borderSoft}`,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>Needs follow-up</span>
                <div style={{ flex: 1 }} />
                <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
                  {d.follow.length}
                </span>
              </div>
              {d.follow.map((f, i) => (
                <div
                  key={i}
                  style={{
                    padding: "10px 14px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    borderBottom: i < d.follow.length - 1 ? `1px solid ${t.borderSoft}` : "none",
                  }}
                >
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: 3,
                      background: f.tone === "bad" ? t.bad : f.tone === "warn" ? t.warn : t.textMute,
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, color: t.text, fontWeight: 500 }}>{f.who}</div>
                    <div style={{ fontSize: 11.5, color: t.textDim, marginTop: 2 }}>{f.action}</div>
                  </div>
                  <span
                    style={{
                      fontFamily: t.fontMono,
                      fontSize: 11,
                      color: f.tone === "bad" ? t.bad : t.textDim,
                    }}
                  >
                    {f.days}d
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 20, marginTop: 20 }}>
          <div
            style={{
              background: t.panel,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "11px 14px",
                borderBottom: `1px solid ${t.borderSoft}`,
                display: "flex",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>Watchlist activity</span>
              <div style={{ flex: 1 }} />
              <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>7 companies</span>
            </div>
            {d.news.map((n, i) => (
              <div
                key={i}
                style={{
                  padding: "9px 14px",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  borderBottom: i < d.news.length - 1 ? `1px solid ${t.borderSoft}` : "none",
                }}
              >
                <Mono name={n.company} t={t} size={16} />
                <span style={{ fontSize: 12.5, color: t.text, fontWeight: 500, width: 84 }}>
                  {n.company}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    color: t.textDim,
                    flex: 1,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {n.text}
                </span>
                <Pill t={t} tone={n.kind === "funding" ? "accent" : "default"}>
                  {n.kind}
                </Pill>
                <span
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 10.5,
                    color: t.textMute,
                    width: 26,
                    textAlign: "right",
                  }}
                >
                  {n.when}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              background: t.panel,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "11px 14px",
                borderBottom: `1px solid ${t.borderSoft}`,
                display: "flex",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>CLI sync</span>
              <div style={{ flex: 1 }} />
              <Pill t={t} tone="accent">
                <span style={{ width: 5, height: 5, borderRadius: 3, background: t.accent }} />
                live
              </Pill>
            </div>
            <div style={{ padding: "6px 0" }}>
              {d.sync.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "4px 14px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    fontFamily: t.fontMono,
                    fontSize: 11,
                  }}
                >
                  <span style={{ color: t.textMute, width: 38 }}>{s.t}</span>
                  <span style={{ color: s.ok ? t.accentInk : t.warn, width: 10 }}>
                    {s.ok ? "→" : "!"}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: t.text }}>{s.cmd}</div>
                    <div style={{ color: t.textDim, marginTop: 1 }}>{s.msg}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
