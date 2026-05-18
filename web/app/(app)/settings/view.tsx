"use client";

import { useState } from "react";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "@/components/chrome/app-shell";
import { Topbar } from "@/components/chrome/topbar";
import { Kbd, Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import type { SettingsData } from "@/lib/types";

export function SettingsView({ data }: { data: SettingsData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);

  return (
    <AppShell>
      <Topbar
        t={t}
        breadcrumbs={["Settings"]}
        right={
          <span
            style={{
              fontFamily: t.fontMono,
              fontSize: 11,
              color: t.textMute,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <icons.terminal size={12} />
            read-only · edit via CLI
          </span>
        }
      />
      <div style={{ flex: 1, overflow: "auto", background: t.bg, padding: "20px 24px 60px" }}>
        <div style={{ maxWidth: 1080, margin: "0 auto", display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 20, alignItems: "start" }}>
          <ScoringSection t={t} data={data} />
          <AutomationSection t={t} data={data} />
          <NotificationsSection t={t} data={data} />
          <ShortcutsSection t={t} data={data} />
        </div>
      </div>
    </AppShell>
  );
}

function SettingsCard({
  t,
  title,
  caption,
  children,
}: {
  t: ReturnType<typeof beaconTokens>;
  title: string;
  caption?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: t.panel,
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: t.text }}>{title}</div>
        {caption && (
          <div style={{ fontSize: 12, color: t.textDim, marginTop: 2, lineHeight: 1.45 }}>
            {caption}
          </div>
        )}
      </div>
      {children}
    </section>
  );
}

function ScoringSection({ t, data }: { t: ReturnType<typeof beaconTokens>; data: SettingsData }) {
  const total = data.scoring.reduce((acc, s) => acc + s.value, 0);
  const allCodeDefined = data.scoring.every((s) => s.isCodeDefined);
  return (
    <SettingsCard
      t={t}
      title="Scoring weights"
      caption={
        allCodeDefined
          ? `Composite weights for AI-first scoring (${total.toFixed(2)} total). Defined in beacon/research/scoring.py — not editable via beacon config.`
          : `Composite weights for AI-first scoring (${total.toFixed(2)} total). Edit via beacon config.`
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {data.scoring.map((s) => {
          const pct = Math.max(0, Math.min(100, (s.value / Math.max(total, 1)) * 100));
          return (
            <div key={s.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontSize: 12.5, color: t.text, display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {s.label}
                  {s.isCodeDefined && (
                    <Pill t={t} tone="ghost" mono>
                      constant
                    </Pill>
                  )}
                </span>
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: t.accentInk }}>
                  {s.value.toFixed(2)}
                </span>
              </div>
              <div
                style={{
                  height: 4,
                  background: t.panelAlt,
                  borderRadius: 2,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: "100%",
                    background: t.accent,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {allCodeDefined ? (
        <div style={{ fontSize: 11.5, color: t.textMute, fontFamily: t.fontMono }}>
          Edit <span style={{ color: t.text }}>beacon/research/scoring.py:WEIGHTS</span> and run{" "}
          <span style={{ color: t.text }}>beacon scores</span> to recompute.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <CliChip t={t} command="beacon config show --json" />
          <CliChip t={t} command="beacon config set scoring.leadership 0.30" />
        </div>
      )}
    </SettingsCard>
  );
}

function AutomationSection({ t, data }: { t: ReturnType<typeof beaconTokens>; data: SettingsData }) {
  const a = data.automation;
  const okRate = a.totalRuns > 0 ? Math.round(((a.totalRuns - a.failedRuns) / a.totalRuns) * 100) : 100;
  return (
    <SettingsCard
      t={t}
      title="Automation"
      caption="Job scans, digests, and signal refreshes. Schedule via beacon automation cron."
    >
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Stat t={t} label="Last run" value={a.lastRunAge} sub={a.lastRunType ?? "—"} ok={a.lastRunOk} />
        <Stat
          t={t}
          label="Total runs"
          value={String(a.totalRuns)}
          sub={`${a.failedRuns} failed`}
        />
        <Stat
          t={t}
          label="Success rate"
          value={`${okRate}%`}
          sub={a.lastDuration != null ? `${a.lastDuration.toFixed(1)}s last run` : ""}
        />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <CliChip t={t} command="beacon automation run" />
        <CliChip t={t} command="beacon automation cron enable --every 60" />
        <CliChip t={t} command="beacon automation log --limit 20 --json" />
      </div>
    </SettingsCard>
  );
}

function NotificationsSection({
  t,
  data,
}: {
  t: ReturnType<typeof beaconTokens>;
  data: SettingsData;
}) {
  return (
    <SettingsCard
      t={t}
      title="Notifications"
      caption="Channels for relevance alerts and digests."
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {data.notifications.map((n) => (
          <div
            key={n.channel}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "8px 10px",
              border: `1px solid ${t.borderSoft}`,
              borderRadius: 5,
              background: t.bg,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 4,
                background: n.enabled ? t.accent : t.textMute,
                boxShadow: n.enabled ? `0 0 6px ${t.accent}` : "none",
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, color: t.text, fontWeight: 500 }}>{n.channel}</div>
              <div style={{ fontSize: 11.5, color: t.textDim }}>{n.detail}</div>
            </div>
            <Pill t={t} tone={n.enabled ? "accent" : "ghost"}>
              {n.enabled ? "on" : "off"}
            </Pill>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <CliChip t={t} command="beacon automation test-notify" />
        <CliChip t={t} command="beacon config set notifications.desktop true" />
      </div>
    </SettingsCard>
  );
}

function ShortcutsSection({
  t,
  data,
}: {
  t: ReturnType<typeof beaconTokens>;
  data: SettingsData;
}) {
  return (
    <SettingsCard
      t={t}
      title="Keyboard shortcuts"
      caption="Global navigation and command palette bindings."
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          rowGap: 10,
          columnGap: 16,
        }}
      >
        {data.shortcuts.map((s) => (
          <div
            key={s.combo}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <span style={{ fontSize: 12.5, color: t.textDim }}>{s.label}</span>
            <span style={{ display: "inline-flex", gap: 4 }}>
              {s.combo.split(" ").map((part, i) => (
                <Kbd key={i} t={t}>
                  {part}
                </Kbd>
              ))}
            </span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11.5, color: t.textMute, fontFamily: t.fontMono, marginTop: 4 }}>
        Config: <span style={{ color: t.text }}>{data.configPath}</span>
        <span style={{ marginLeft: 8 }}>
          DB: <span style={{ color: t.text }}>{data.dbPath}</span>
        </span>
      </div>
    </SettingsCard>
  );
}

function Stat({
  t,
  label,
  value,
  sub,
  ok,
}: {
  t: ReturnType<typeof beaconTokens>;
  label: string;
  value: string;
  sub: string;
  ok?: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 110 }}>
      <span
        style={{
          fontFamily: t.fontMono,
          fontSize: 10.5,
          color: t.textMute,
          letterSpacing: 0.6,
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 18,
          fontWeight: 500,
          color: ok === false ? t.bad : t.text,
          letterSpacing: -0.5,
        }}
      >
        {value}
      </span>
      {sub && <span style={{ fontSize: 11, color: t.textDim }}>{sub}</span>}
    </div>
  );
}

function CliChip({ t, command }: { t: ReturnType<typeof beaconTokens>; command: string }) {
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
        gap: 8,
        padding: "7px 10px",
        background: t.bg,
        border: `1px dashed ${t.border}`,
        borderRadius: 5,
        cursor: "pointer",
        fontFamily: t.fontMono,
        fontSize: 11.5,
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
      <span style={{ color: copied ? t.accentInk : t.textMute, fontSize: 10.5 }}>
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}
