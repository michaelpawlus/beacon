"use client";

import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "@/components/chrome/app-shell";
import { Topbar } from "@/components/chrome/topbar";
import { JobCardSwatch, type JobCardVariant } from "./job-card-swatch";
import type { BeaconData } from "@/lib/types";

const VARIANTS: Array<{ k: JobCardVariant; label: string; caption: string; w: number; h: number }> = [
  { k: "row",      label: "Row",      caption: "Dense list item",     w: 440, h: 140 },
  { k: "stacked",  label: "Stacked",  caption: "Full card",            w: 340, h: 260 },
  { k: "brief",    label: "Brief",    caption: "Editorial",            w: 400, h: 260 },
  { k: "terminal", label: "Terminal", caption: "Mono record",          w: 400, h: 260 },
];

export function JobsView({ data }: { data: BeaconData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);
  const job = data.newMatches[0];

  return (
    <AppShell>
      <Topbar t={t} breadcrumbs={["Jobs", "Card variations"]} />
      <div style={{ flex: 1, overflow: "auto", padding: "28px 32px 60px", background: t.bg }}>
        <div style={{ maxWidth: 1100, marginBottom: 24 }}>
          <div
            style={{
              fontFamily: t.fontMono,
              fontSize: 11,
              letterSpacing: 1,
              color: t.textDim,
              textTransform: "uppercase",
            }}
          >
            Job card layouts
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: t.text,
              letterSpacing: -0.5,
              marginTop: 6,
            }}
          >
            Same match. Pick the row that feels right.
          </div>
          <div style={{ fontSize: 13, color: t.textDim, marginTop: 6 }}>
            {job ? `${job.company} · ${job.title} · ${job.score}` : "No matches yet — run a scan."}
          </div>
        </div>

        {job && (
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            {VARIANTS.map((v) => (
              <div key={v.k} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 8,
                    fontFamily: t.fontMono,
                    fontSize: 11,
                    color: t.textDim,
                    letterSpacing: 0.5,
                    textTransform: "uppercase",
                  }}
                >
                  <span style={{ color: t.text, fontWeight: 500 }}>{v.label}</span>
                  <span>·</span>
                  <span>{v.caption}</span>
                </div>
                <div
                  style={{
                    width: v.w,
                    height: v.h,
                    border: `1px dashed ${t.border}`,
                    borderRadius: 8,
                    overflow: "hidden",
                  }}
                >
                  <JobCardSwatch variant={v.k} t={t} job={job} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
