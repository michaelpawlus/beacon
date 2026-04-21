"use client";

import type { Tokens } from "@/lib/tokens";
import { Mono, Pill } from "@/components/primitives";
import type { BeaconData, PipelineEntry } from "@/lib/types";

type Row = {
  co: string;
  role: string;
  stage: PipelineEntry["stage"];
  since: number;
  next: string;
  tone: "default" | "warn" | "bad" | "accent";
};

const FALLBACK_ROWS: Row[] = [
  { co: "Vercel",    role: "Staff FE",       stage: "Screen",  since: 3,  next: "Recruiter call Thu · 2p", tone: "default" },
  { co: "Ramp",      role: "Sr Product Eng", stage: "Onsite",  since: 1,  next: "Onsite loop Apr 28",      tone: "accent" },
  { co: "Notion AI", role: "Applied AI",     stage: "Applied", since: 11, next: "Follow up · ghost risk",  tone: "bad" },
  { co: "Replit",    role: "Design Eng",     stage: "Applied", since: 6,  next: "Awaiting response",       tone: "default" },
  { co: "Harvey",    role: "ML Platform",    stage: "Screen",  since: 2,  next: "Take-home due Fri",       tone: "warn" },
  { co: "Scale",     role: "Staff Eng",      stage: "Saved",   since: 2,  next: "—",                       tone: "default" },
  { co: "Modal",     role: "Platform",       stage: "Screen",  since: 5,  next: "Awaiting scheduling",     tone: "default" },
  { co: "Stripe",    role: "Staff FE",       stage: "Closed",  since: 40, next: "Rejected · post-onsite",  tone: "default" },
];

export function PipelineList({ t, data }: { t: Tokens; data: BeaconData }) {
  const rows: Row[] = data.pipeline.length
    ? data.pipeline.map((p) => ({
        co: p.company,
        role: p.role,
        stage: p.stage,
        since: p.since,
        next: p.next,
        tone: p.ghost ? "bad" : p.stage === "Onsite" ? "accent" : p.since >= 5 ? "warn" : "default",
      }))
    : FALLBACK_ROWS;

  return (
    <div style={{ background: t.bg, color: t.text, fontFamily: t.fontSans, padding: 16, flex: 1, overflow: "auto" }}>
      <div
        style={{
          background: t.panel,
          border: `1px solid ${t.border}`,
          borderRadius: 6,
          overflow: "hidden",
          maxWidth: 900,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.2fr 1.2fr 90px 80px 1.5fr",
            gap: 10,
            padding: "9px 14px",
            borderBottom: `1px solid ${t.border}`,
            fontSize: 10.5,
            color: t.textMute,
            letterSpacing: 0.6,
            textTransform: "uppercase",
          }}
        >
          <span>Company</span>
          <span>Role</span>
          <span>Stage</span>
          <span>In stage</span>
          <span>Next</span>
        </div>
        {rows.map((r, i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "1.2fr 1.2fr 90px 80px 1.5fr",
              gap: 10,
              padding: "10px 14px",
              alignItems: "center",
              borderBottom: i < rows.length - 1 ? `1px solid ${t.borderSoft}` : "none",
              fontSize: 12.5,
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
              <Mono name={r.co} t={t} size={14} radius={3} />
              <span style={{ color: t.text, fontWeight: 500 }}>{r.co}</span>
            </span>
            <span style={{ color: t.textDim }}>{r.role}</span>
            <Pill t={t} tone={r.stage === "Onsite" ? "accent" : "default"}>
              {r.stage}
            </Pill>
            <span
              style={{
                fontFamily: t.fontMono,
                fontSize: 11.5,
                color: r.tone === "bad" ? t.bad : r.tone === "warn" ? t.warn : t.textDim,
              }}
            >
              {r.since}d
            </span>
            <span
              style={{
                fontSize: 12,
                color: r.tone === "bad" ? t.bad : r.tone === "accent" ? t.accentInk : t.textDim,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {r.next}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
