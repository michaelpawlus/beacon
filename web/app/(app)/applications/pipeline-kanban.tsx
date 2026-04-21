"use client";

import type { Tokens } from "@/lib/tokens";
import { Mono, Pill } from "@/components/primitives";
import type { BeaconData, PipelineEntry } from "@/lib/types";

type Stage = PipelineEntry["stage"];
const COLS: Stage[] = ["Saved", "Applied", "Screen", "Onsite", "Offer", "Closed"];

// Supplemental filler entries so the kanban reads visually when the DB is thin.
const FILLERS: Record<Stage, Array<Pick<PipelineEntry, "id" | "company" | "role" | "since" | "ghost">>> = {
  Saved: [
    { id: "f-saved-1", company: "Scale", role: "Staff Eng", since: 2, ghost: false },
    { id: "f-saved-2", company: "Glean", role: "Design Eng", since: 4, ghost: false },
  ],
  Applied: [],
  Screen: [{ id: "f-screen-1", company: "Modal", role: "Platform", since: 5, ghost: false }],
  Onsite: [],
  Offer: [],
  Closed: [{ id: "f-closed-1", company: "Stripe", role: "Staff FE", since: 40, ghost: false }],
};

export function PipelineKanban({ t, data }: { t: Tokens; data: BeaconData }) {
  const byStage: Record<Stage, Array<PipelineEntry | (typeof FILLERS)[Stage][number]>> = Object.fromEntries(
    COLS.map((c) => [c, [] as Array<PipelineEntry | (typeof FILLERS)[Stage][number]>]),
  ) as Record<Stage, Array<PipelineEntry | (typeof FILLERS)[Stage][number]>>;

  data.pipeline.forEach((a) => {
    if (byStage[a.stage]) byStage[a.stage].push(a);
  });
  COLS.forEach((c) => {
    if (byStage[c].length < 2) byStage[c].push(...FILLERS[c]);
  });

  const counts = COLS.map((c) => byStage[c].length);

  return (
    <div
      style={{
        background: t.bg,
        color: t.text,
        fontFamily: t.fontSans,
        padding: 16,
        flex: 1,
        boxSizing: "border-box",
        display: "flex",
        gap: 10,
        overflow: "hidden",
      }}
    >
      {COLS.map((c, i) => (
        <div
          key={c}
          style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 8 }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "0 2px" }}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 4,
                background: c === "Offer" ? t.accent : c === "Closed" ? t.textMute : t.border,
              }}
            />
            <span style={{ fontSize: 12, fontWeight: 500, color: t.text }}>{c}</span>
            <span style={{ fontFamily: t.fontMono, fontSize: 10.5, color: t.textMute }}>{counts[i]}</span>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              overflowY: "auto",
              flex: 1,
            }}
          >
            {byStage[c].map((a) => (
              <div
                key={a.id}
                style={{
                  background: t.panel,
                  border: `1px solid ${t.border}`,
                  borderRadius: 5,
                  padding: "8px 9px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Mono name={a.company} t={t} size={13} radius={3} />
                  <span
                    style={{
                      fontSize: 11.5,
                      fontWeight: 500,
                      color: t.text,
                      minWidth: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {a.company}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 10.5,
                    color: t.textDim,
                    marginTop: 3,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {a.role}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 6 }}>
                  <span
                    style={{
                      fontFamily: t.fontMono,
                      fontSize: 9.5,
                      color: a.ghost ? t.bad : t.textMute,
                    }}
                  >
                    {a.since}d
                  </span>
                  {a.ghost && (
                    <Pill t={t} tone="bad">
                      stale
                    </Pill>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
