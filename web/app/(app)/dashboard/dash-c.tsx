"use client";

import type { ReactNode } from "react";
import type { Tokens } from "@/lib/tokens";
import type { BeaconData } from "@/lib/types";
import { Kbd, Mono, Pill } from "@/components/primitives";
import { Topbar } from "@/components/chrome/topbar";

function CardHeader({
  t,
  label,
  right,
  mono,
}: {
  t: Tokens;
  label: string;
  right?: ReactNode;
  mono?: boolean;
}) {
  return (
    <div
      style={{
        padding: "8px 12px",
        borderBottom: `1px solid ${t.borderSoft}`,
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: 3, background: t.textMute }} />
      <span
        style={{
          fontFamily: mono ? t.fontMono : t.fontSans,
          fontSize: 12,
          color: t.text,
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <div style={{ flex: 1 }} />
      {right}
    </div>
  );
}

function Row({
  t,
  cells,
  widths,
  head,
}: {
  t: Tokens;
  cells: ReactNode[];
  widths: string[];
  head?: boolean;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: widths.join(" "),
        gap: 10,
        padding: "6px 12px",
        borderBottom: `1px solid ${head ? t.border : t.borderSoft}`,
        color: head ? t.textMute : t.textDim,
        fontSize: head ? 10.5 : 11.5,
        letterSpacing: head ? 0.6 : 0,
        textTransform: head ? "uppercase" : "none",
        alignItems: "center",
      }}
    >
      {cells.map((c, i) => (
        <div
          key={i}
          style={{
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {c}
        </div>
      ))}
    </div>
  );
}

export function DashC({ t, data }: { t: Tokens; data: BeaconData }) {
  const d = data;
  const stages: Array<"Saved" | "Applied" | "Screen" | "Onsite" | "Offer" | "Closed"> = [
    "Saved",
    "Applied",
    "Screen",
    "Onsite",
    "Offer",
    "Closed",
  ];
  const counts = stages.map((s) => d.pipeline.filter((p) => p.stage === s).length);
  // pad with static values to match visual density when DB empty
  const display = counts.map((c, i) => c || [7, 4, 2, 1, 0, 3][i]);

  return (
    <>
      <Topbar
        t={t}
        breadcrumbs={["~", "dashboard"]}
        variant="mono"
        right={
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontFamily: t.fontMono,
              fontSize: 11,
              color: t.textDim,
            }}
          >
            <span style={{ color: t.accent }}>●</span>
            <span>cli daemon · pid 48210</span>
          </div>
        }
      />

      <div
        style={{
          padding: "10px 16px",
          borderBottom: `1px solid ${t.borderSoft}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          background: t.panel,
        }}
      >
        <span style={{ fontFamily: t.fontMono, fontSize: 12, color: t.accentInk }}>$</span>
        <span style={{ fontFamily: t.fontMono, fontSize: 12, color: t.text, flex: 1 }}>
          beacon status <span style={{ color: t.textMute }}>--watchlist --since=24h</span>
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {["pull", "rank", "enrich", "apply"].map((c) => (
            <span
              key={c}
              style={{
                fontFamily: t.fontMono,
                fontSize: 11,
                padding: "3px 8px",
                border: `1px solid ${t.border}`,
                borderRadius: 4,
                color: t.textDim,
                background: t.bg,
              }}
            >
              {c}
            </span>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <div
          style={{
            fontFamily: t.fontMono,
            fontSize: 12,
            color: t.textDim,
            marginBottom: 14,
            lineHeight: 1.7,
          }}
        >
          <span style={{ color: t.textMute }}># </span>
          <span>
            watchlist=94 · matches={d.newMatches.length} new ·{" "}
          </span>
          <span style={{ color: t.accentInk }}>
            above_threshold={d.newMatches.filter((m) => m.score >= 85).length}
          </span>{" "}
          · <span>pipeline={d.pipeline.length} open</span> ·{" "}
          <span style={{ color: t.warn }}>
            ghosted={d.pipeline.filter((p) => p.ghost).length}
          </span>{" "}
          · <span>interviews={d.interviews.length} scheduled</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 12 }}>
          <div
            style={{
              gridColumn: "span 8",
              border: `1px solid ${t.border}`,
              borderRadius: 4,
              background: t.panel,
            }}
          >
            <CardHeader
              t={t}
              mono
              label="matches.json"
              right={
                <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>sort=score desc</span>
              }
            />
            <div style={{ fontFamily: t.fontMono, fontSize: 11.5 }}>
              <Row
                t={t}
                head
                cells={["score", "company", "role", "stack", "comp", "age"]}
                widths={["50px", "110px", "1fr", "180px", "120px", "40px"]}
              />
              {d.newMatches.map((j) => (
                <Row
                  key={j.id}
                  t={t}
                  widths={["50px", "110px", "1fr", "180px", "120px", "40px"]}
                  cells={[
                    <span
                      key="s"
                      style={{
                        color: j.score >= 85 ? t.accentInk : j.score >= 70 ? t.warn : t.textDim,
                      }}
                    >
                      {j.score}
                    </span>,
                    <span
                      key="c"
                      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                    >
                      <Mono name={j.company} t={t} size={12} radius={2} />
                      <span style={{ color: t.text }}>
                        {j.company.toLowerCase().replace(/\s/g, "")}
                      </span>
                    </span>,
                    <span
                      key="r"
                      style={{
                        color: t.text,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {j.title} {j.referral && <span style={{ color: t.accent }}>✦</span>}
                    </span>,
                    <span
                      key="st"
                      style={{
                        color: t.textDim,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {j.stack.join(",")}
                    </span>,
                    <span key="cp" style={{ color: t.textDim }}>
                      {j.comp}
                    </span>,
                    <span key="a" style={{ color: t.textMute }}>
                      {j.posted}
                    </span>,
                  ]}
                />
              ))}
              <div
                style={{
                  padding: "8px 12px",
                  fontFamily: t.fontMono,
                  fontSize: 11,
                  color: t.textDim,
                  display: "flex",
                  gap: 10,
                  borderTop: `1px solid ${t.borderSoft}`,
                }}
              >
                <span>
                  <Kbd t={t}>j</Kbd> <Kbd t={t}>k</Kbd> move
                </span>
                <span>
                  <Kbd t={t}>⏎</Kbd> open
                </span>
                <span>
                  <Kbd t={t}>a</Kbd> apply
                </span>
                <span>
                  <Kbd t={t}>/</Kbd> filter
                </span>
                <div style={{ flex: 1 }} />
                <span>1–{Math.min(6, d.newMatches.length)} of {d.newMatches.length}</span>
              </div>
            </div>
          </div>

          <div
            style={{
              gridColumn: "span 4",
              border: `1px solid ${t.border}`,
              borderRadius: 4,
              background: t.panel,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <CardHeader
              t={t}
              mono
              label="sync.log"
              right={
                <Pill t={t} tone="accent">
                  live
                </Pill>
              }
            />
            <div
              style={{
                flex: 1,
                padding: "4px 0",
                fontFamily: t.fontMono,
                fontSize: 11,
                lineHeight: 1.55,
              }}
            >
              {d.sync.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "3px 12px",
                    display: "grid",
                    gridTemplateColumns: "38px 14px 1fr",
                    gap: 6,
                    alignItems: "start",
                  }}
                >
                  <span style={{ color: t.textMute }}>{s.t}</span>
                  <span style={{ color: s.ok ? t.accent : t.warn }}>{s.ok ? "✓" : "!"}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: t.text }}>{s.cmd}</div>
                    <div style={{ color: t.textDim }}>{s.msg}</div>
                  </div>
                </div>
              ))}
              <div style={{ padding: "6px 12px", color: t.textMute }}>
                <span style={{ color: t.accentInk }}>$</span>{" "}
                <span
                  style={{
                    background: t.accentInk,
                    width: 7,
                    height: 12,
                    display: "inline-block",
                    verticalAlign: -2,
                  }}
                />
              </div>
            </div>
          </div>

          <div
            style={{
              gridColumn: "span 8",
              border: `1px solid ${t.border}`,
              borderRadius: 4,
              background: t.panel,
            }}
          >
            <CardHeader
              t={t}
              mono
              label="pipeline"
              right={
                <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
                  {d.pipeline.length} open · {d.pipeline.filter((p) => p.ghost).length} ghosted
                </span>
              }
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(6, 1fr)",
                gap: 1,
                background: t.borderSoft,
                borderTop: `1px solid ${t.borderSoft}`,
              }}
            >
              {stages.map((s, i) => (
                <div key={s} style={{ background: t.panel, padding: "10px 12px" }}>
                  <div
                    style={{
                      fontFamily: t.fontMono,
                      fontSize: 10,
                      color: t.textMute,
                      letterSpacing: 0.6,
                      textTransform: "uppercase",
                    }}
                  >
                    {String(i).padStart(2, "0")} {s}
                  </div>
                  <div
                    style={{
                      fontFamily: t.fontMono,
                      fontSize: 20,
                      color: t.text,
                      fontWeight: 500,
                      marginTop: 3,
                    }}
                  >
                    {display[i]}
                  </div>
                  <div
                    style={{
                      height: 2,
                      width: "100%",
                      background: t.borderSoft,
                      marginTop: 6,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${display[i] * 14}%`,
                        height: "100%",
                        background: s === "Closed" ? t.textMute : t.accent,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            {d.pipeline.slice(0, 6).map((a) => (
              <div
                key={a.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "18px 110px 1fr 90px 1fr 60px",
                  gap: 10,
                  alignItems: "center",
                  padding: "8px 12px",
                  borderTop: `1px solid ${t.borderSoft}`,
                  fontFamily: t.fontMono,
                  fontSize: 11.5,
                }}
              >
                <span style={{ color: a.ghost ? t.bad : t.textMute }}>{a.ghost ? "▲" : "·"}</span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    color: t.text,
                  }}
                >
                  <Mono name={a.company} t={t} size={12} radius={2} />
                  {a.company}
                </span>
                <span
                  style={{
                    color: t.textDim,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {a.role}
                </span>
                <Pill t={t} tone={a.stage === "Onsite" ? "accent" : "default"} mono>
                  {a.stage}
                </Pill>
                <span
                  style={{
                    color: a.ghost ? t.bad : t.textDim,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {a.next}
                </span>
                <span style={{ color: t.textMute, textAlign: "right" }}>{a.since}d</span>
              </div>
            ))}
          </div>

          <div
            style={{
              gridColumn: "span 4",
              border: `1px solid ${t.border}`,
              borderRadius: 4,
              background: t.panel,
            }}
          >
            <CardHeader
              t={t}
              mono
              label="watchlist.news"
              right={<span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>72h</span>}
            />
            {d.news.map((n, i) => (
              <div
                key={i}
                style={{
                  padding: "8px 12px",
                  borderTop: `1px solid ${t.borderSoft}`,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                }}
              >
                <span
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 10,
                    color: t.textMute,
                    width: 28,
                    paddingTop: 2,
                  }}
                >
                  {n.when}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: t.fontMono, fontSize: 11.5, color: t.text }}>
                    {n.company.toLowerCase()}
                    <span style={{ color: t.textMute }}>/{n.kind}</span>
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: t.textDim,
                      marginTop: 2,
                      textWrap: "pretty" as React.CSSProperties["textWrap"],
                    }}
                  >
                    {n.text}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            marginTop: 14,
            padding: "10px 12px",
            borderRadius: 4,
            border: `1px solid ${t.border}`,
            background: t.panel,
            fontFamily: t.fontMono,
            fontSize: 12,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span style={{ color: t.accentInk }}>beacon ❯</span>
          <span style={{ color: t.textMute }}>type a command or press</span>
          <Kbd t={t}>⌘K</Kbd>
          <div style={{ flex: 1 }} />
          <span style={{ color: t.textMute }}>next sync · 3m</span>
        </div>
      </div>
    </>
  );
}
