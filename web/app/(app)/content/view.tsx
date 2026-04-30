"use client";

import { useMemo, useState } from "react";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "@/components/chrome/app-shell";
import { Topbar } from "@/components/chrome/topbar";
import { Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import type { ContentAlert, ContentCalendarItem, ContentData, ContentDraft } from "@/lib/types";

const DRAFT_STAGES: Array<{ key: ContentDraft["status"]; label: string; tone: "default" | "warn" | "accent" }> = [
  { key: "draft", label: "Draft", tone: "default" },
  { key: "published", label: "Published", tone: "accent" },
  { key: "archived", label: "Archived", tone: "warn" },
];

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function buildWeekStrip(items: ContentCalendarItem[]) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(start.getDate() - start.getDay());
  const cells: Array<{ date: Date; iso: string; items: ContentCalendarItem[] }> = [];
  for (let i = 0; i < 14; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const iso = d.toISOString().slice(0, 10);
    cells.push({
      date: d,
      iso,
      items: items.filter((it) => it.targetDate?.slice(0, 10) === iso),
    });
  }
  return cells;
}

export function ContentView({ data }: { data: ContentData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);

  const draftsByStage = useMemo(() => {
    const map = new Map<string, ContentDraft[]>();
    for (const stage of DRAFT_STAGES) map.set(stage.key, []);
    for (const d of data.drafts) {
      const list = map.get(d.status) ?? map.get("draft")!;
      list.push(d);
    }
    return map;
  }, [data.drafts]);

  const cells = useMemo(() => buildWeekStrip(data.calendar), [data.calendar]);

  return (
    <AppShell>
      <Topbar t={t} breadcrumbs={["Content"]} />
      <div style={{ flex: 1, overflow: "auto", background: t.bg, padding: "20px 24px 60px" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
          <CalendarStrip t={t} cells={cells} />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) 320px",
              gap: 20,
              alignItems: "start",
            }}
          >
            <DraftsKanban t={t} draftsByStage={draftsByStage} />
            <AlertsPane t={t} alerts={data.alerts} resumes={data.resumes} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function CalendarStrip({
  t,
  cells,
}: {
  t: ReturnType<typeof beaconTokens>;
  cells: Array<{ date: Date; iso: string; items: ContentCalendarItem[] }>;
}) {
  const todayIso = new Date().toISOString().slice(0, 10);
  return (
    <div>
      <SectionHeader t={t} title="Calendar · next 14 days" cli="beacon presence calendar --json" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(14, minmax(0, 1fr))",
          gap: 6,
          marginTop: 12,
        }}
      >
        {cells.map((cell) => {
          const isToday = cell.iso === todayIso;
          return (
            <div
              key={cell.iso}
              style={{
                background: t.panel,
                border: `1px solid ${isToday ? t.accent : t.border}`,
                borderRadius: 6,
                padding: "8px 8px",
                minHeight: 92,
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontFamily: t.fontMono,
                  fontSize: 10.5,
                  color: isToday ? t.accentInk : t.textMute,
                }}
              >
                <span style={{ textTransform: "uppercase" }}>
                  {cell.date.toLocaleDateString(undefined, { weekday: "short" })}
                </span>
                <span>{cell.date.getDate()}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {cell.items.map((it) => (
                  <div
                    key={it.id}
                    style={{
                      fontSize: 10.5,
                      lineHeight: 1.3,
                      color: t.text,
                      background: t.panelAlt,
                      borderLeft: `2px solid ${
                        it.status === "drafted" ? t.accent : it.status === "outlined" ? t.warn : t.textMute
                      }`,
                      padding: "3px 5px",
                      borderRadius: 3,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={it.title}
                  >
                    {it.title}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DraftsKanban({
  t,
  draftsByStage,
}: {
  t: ReturnType<typeof beaconTokens>;
  draftsByStage: Map<string, ContentDraft[]>;
}) {
  return (
    <div>
      <SectionHeader t={t} title="Drafts" cli="beacon presence drafts --json" />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
          marginTop: 12,
          alignItems: "start",
        }}
      >
        {DRAFT_STAGES.map((stage) => {
          const list = draftsByStage.get(stage.key) ?? [];
          return (
            <div
              key={stage.key}
              style={{
                background: t.panel,
                border: `1px solid ${t.border}`,
                borderRadius: 6,
                display: "flex",
                flexDirection: "column",
                minHeight: 200,
              }}
            >
              <div
                style={{
                  padding: "10px 12px",
                  borderBottom: `1px solid ${t.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 500, color: t.text }}>{stage.label}</span>
                <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
                  {list.length}
                </span>
              </div>
              <div
                style={{
                  padding: 10,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                {list.length === 0 ? (
                  <div style={{ color: t.textMute, fontSize: 11.5, padding: "16px 4px", textAlign: "center" }}>
                    None
                  </div>
                ) : (
                  list.map((d) => <DraftCard key={d.id} t={t} d={d} />)
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DraftCard({ t, d }: { t: ReturnType<typeof beaconTokens>; d: ContentDraft }) {
  const stale = d.status === "draft" && d.daysSinceUpdate >= 21;
  const warn = d.status === "draft" && d.daysSinceUpdate >= 10 && !stale;
  return (
    <div
      style={{
        background: t.bg,
        border: `1px solid ${stale ? t.bad : warn ? t.warn : t.border}`,
        borderRadius: 5,
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <Pill t={t} tone="ghost" mono>
          {d.platform}
        </Pill>
        <Pill t={t} tone="ghost">
          {d.contentType.replace(/_/g, " ")}
        </Pill>
        <span style={{ flex: 1 }} />
        <span
          style={{
            fontFamily: t.fontMono,
            fontSize: 10.5,
            color: stale ? t.bad : warn ? t.warn : t.textMute,
          }}
        >
          {d.daysSinceUpdate}d
        </span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 500, color: t.text, lineHeight: 1.35 }}>{d.title}</div>
      {d.preview && (
        <div
          style={{
            fontSize: 11.5,
            color: t.textDim,
            lineHeight: 1.45,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {d.preview}
        </div>
      )}
      <CliChip t={t} command={`beacon presence draft ${d.id}`} compact />
    </div>
  );
}

function AlertsPane({
  t,
  alerts,
  resumes,
}: {
  t: ReturnType<typeof beaconTokens>;
  alerts: ContentAlert[];
  resumes: ContentData["resumes"];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <SectionHeader t={t} title="Staleness alerts" cli={null} />
        <div
          style={{
            marginTop: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {alerts.length === 0 ? (
            <div
              style={{
                background: t.panel,
                border: `1px dashed ${t.border}`,
                borderRadius: 6,
                padding: "14px 12px",
                color: t.textDim,
                fontSize: 12,
                textAlign: "center",
              }}
            >
              <span style={{ color: t.accentInk }}>✓</span> Nothing stale right now
            </div>
          ) : (
            alerts.map((a, i) => <AlertCard key={`${a.kind}-${i}`} t={t} a={a} />)
          )}
        </div>
      </div>

      <div>
        <SectionHeader t={t} title="Resume variants" cli="beacon report variant-effectiveness --json" />
        <div
          style={{
            marginTop: 12,
            background: t.panel,
            border: `1px solid ${t.border}`,
            borderRadius: 6,
            overflow: "hidden",
          }}
        >
          {resumes.length === 0 ? (
            <div style={{ padding: "14px 12px", color: t.textMute, fontSize: 11.5, textAlign: "center" }}>
              No variants tracked
            </div>
          ) : (
            resumes.map((v, i) => (
              <div
                key={v.variantLabel}
                style={{
                  padding: "10px 12px",
                  borderBottom: i < resumes.length - 1 ? `1px solid ${t.borderSoft}` : "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, color: t.text, fontWeight: 500 }}>{v.variantLabel}</div>
                  <div style={{ fontSize: 11, color: t.textMute, fontFamily: t.fontMono }}>
                    {v.count} runs · {fmtDate(v.lastCreated)}
                  </div>
                </div>
                <span
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 11.5,
                    color: v.daysSince >= 30 ? t.bad : v.daysSince >= 14 ? t.warn : t.textDim,
                  }}
                >
                  {v.daysSince}d
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function AlertCard({ t, a }: { t: ReturnType<typeof beaconTokens>; a: ContentAlert }) {
  const accent = a.tone === "bad" ? t.bad : a.tone === "warn" ? t.warn : t.textMute;
  return (
    <div
      style={{
        background: t.panel,
        border: `1px solid ${t.border}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: 6,
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 12.5, color: t.text, fontWeight: 500, lineHeight: 1.35 }}>{a.title}</div>
      <div style={{ fontSize: 11.5, color: t.textDim, lineHeight: 1.4 }}>{a.detail}</div>
      <CliChip t={t} command={a.cli} compact />
    </div>
  );
}

function SectionHeader({
  t,
  title,
  cli,
}: {
  t: ReturnType<typeof beaconTokens>;
  title: string;
  cli: string | null;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
      <div
        style={{
          fontFamily: t.fontMono,
          fontSize: 11,
          color: t.textDim,
          letterSpacing: 0.6,
          textTransform: "uppercase",
        }}
      >
        {title}
      </div>
      {cli && (
        <div
          style={{
            fontFamily: t.fontMono,
            fontSize: 11,
            color: t.textMute,
          }}
        >
          <span style={{ color: t.accentInk }}>$</span> {cli}
        </div>
      )}
    </div>
  );
}

function CliChip({
  t,
  command,
  compact = false,
}: {
  t: ReturnType<typeof beaconTokens>;
  command: string;
  compact?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: compact ? "5px 8px" : "8px 12px",
        background: t.panelAlt,
        border: `1px dashed ${t.border}`,
        borderRadius: 4,
        cursor: "pointer",
        fontFamily: t.fontMono,
        fontSize: compact ? 11 : 12,
        color: t.text,
        textAlign: "left",
        width: "100%",
      }}
      title="Copy to clipboard"
    >
      <span style={{ color: t.accentInk }}>$</span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {command}
      </span>
      <span style={{ color: copied ? t.accentInk : t.textMute, fontSize: compact ? 10 : 11 }}>
        {copied ? "copied" : <icons.terminal size={11} />}
      </span>
    </button>
  );
}
