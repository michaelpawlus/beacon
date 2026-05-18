"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "@/components/chrome/app-shell";
import { Topbar } from "@/components/chrome/topbar";
import { Mono, Pill } from "@/components/primitives";
import { icons } from "@/components/icons";
import type { CompaniesData, Company, DiscoveryCandidate, DiscoveryData } from "@/lib/types";

type SortKey = "tier" | "score" | "name" | "openJobs" | "lastResearched";

const SORT_LABEL: Record<SortKey, string> = {
  tier: "Tier",
  score: "Score",
  name: "Name",
  openJobs: "Open Jobs",
  lastResearched: "Last Scanned",
};

function tierTone(tier: number): "accent" | "warn" | "default" | "ghost" {
  if (tier === 1) return "accent";
  if (tier === 2) return "warn";
  if (tier === 3) return "default";
  return "ghost";
}

function compareCompanies(a: Company, b: Company, sort: SortKey, dir: 1 | -1): number {
  const mul = dir;
  switch (sort) {
    case "tier":
      return mul * ((a.tier - b.tier) || (b.score - a.score));
    case "score":
      return mul * ((b.score - a.score) || (a.tier - b.tier));
    case "name":
      return mul * a.name.localeCompare(b.name);
    case "openJobs":
      return mul * ((b.openJobs - a.openJobs) || (a.name.localeCompare(b.name)));
    case "lastResearched": {
      const at = a.lastResearchedAt ? new Date(a.lastResearchedAt).getTime() : 0;
      const bt = b.lastResearchedAt ? new Date(b.lastResearchedAt).getTime() : 0;
      return mul * (bt - at);
    }
  }
}

export function CompaniesView({ data }: { data: CompaniesData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);
  const router = useRouter();
  const sp = useSearchParams();

  const tierParam = sp.get("tier");
  const minScoreParam = sp.get("minScore");
  const toolsParam = sp.get("tools");
  const sortParam = (sp.get("sort") as SortKey | null) ?? "tier";
  const dirParam: 1 | -1 = sp.get("dir") === "asc" ? 1 : sort_dir(sortParam);
  const selectedId = sp.get("id");

  const tier = tierParam ? Number(tierParam) : null;
  const minScore = minScoreParam ? Number(minScoreParam) : null;
  const tools = useMemo(
    () => (toolsParam ? toolsParam.split(",").filter(Boolean) : []),
    [toolsParam],
  );

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(sp.toString());
    if (value == null || value === "") next.delete(key);
    else next.set(key, value);
    router.replace(`/companies?${next.toString()}`, { scroll: false });
  }

  function toggleTool(name: string) {
    const set = new Set(tools);
    if (set.has(name)) set.delete(name);
    else set.add(name);
    setParam("tools", set.size ? Array.from(set).join(",") : null);
  }

  function setSort(k: SortKey) {
    if (k === sortParam) {
      setParam("dir", dirParam === 1 ? "desc" : "asc");
    } else {
      setParam("sort", k);
      setParam("dir", null);
    }
  }

  const filtered = useMemo(() => {
    let list = data.companies;
    if (tier != null) list = list.filter((c) => c.tier === tier);
    if (minScore != null) list = list.filter((c) => c.score >= minScore);
    if (tools.length) {
      list = list.filter((c) => {
        const names = c.toolsList.map((tt) => tt.name.toLowerCase());
        return tools.every((t) => names.some((n) => n.includes(t.toLowerCase())));
      });
    }
    return [...list].sort((a, b) => compareCompanies(a, b, sortParam, dirParam));
  }, [data.companies, tier, minScore, tools, sortParam, dirParam]);

  const selected = selectedId ? data.companies.find((c) => String(c.id) === selectedId) ?? null : null;

  return (
    <AppShell>
      <Topbar
        t={t}
        breadcrumbs={["Companies"]}
        right={
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontFamily: t.fontMono,
              fontSize: 11,
              color: t.textDim,
            }}
          >
            <span style={{ color: t.textMute }}>{filtered.length}</span>
            <span>of</span>
            <span style={{ color: t.textMute }}>{data.companies.length}</span>
          </div>
        }
      />
      <div style={{ flex: 1, overflow: "auto", background: t.bg, padding: "20px 24px 60px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          {data.discovery.pendingCount > 0 && (
            <DiscoveryRail t={t} discovery={data.discovery} />
          )}
          <FilterBar
            t={t}
            tier={tier}
            minScore={minScore}
            tools={tools}
            allTools={data.totalTools}
            setParam={setParam}
            toggleTool={toggleTool}
          />

          <div
            style={{
              marginTop: 16,
              background: t.panel,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "60px 70px 1.4fr 1.6fr 80px 110px 36px",
                gap: 10,
                padding: "10px 14px",
                borderBottom: `1px solid ${t.border}`,
                fontSize: 10.5,
                color: t.textMute,
                letterSpacing: 0.6,
                textTransform: "uppercase",
              }}
            >
              <SortHeader k="tier" sort={sortParam} dir={dirParam} t={t} onClick={setSort}>
                Tier
              </SortHeader>
              <SortHeader k="score" sort={sortParam} dir={dirParam} t={t} onClick={setSort}>
                Score
              </SortHeader>
              <SortHeader k="name" sort={sortParam} dir={dirParam} t={t} onClick={setSort}>
                Name
              </SortHeader>
              <span>Tools</span>
              <SortHeader k="openJobs" sort={sortParam} dir={dirParam} t={t} onClick={setSort}>
                Open
              </SortHeader>
              <SortHeader k="lastResearched" sort={sortParam} dir={dirParam} t={t} onClick={setSort}>
                Scanned
              </SortHeader>
              <span />
            </div>
            {filtered.length === 0 ? (
              <div style={{ padding: "32px 14px", textAlign: "center", color: t.textDim, fontSize: 13 }}>
                No companies match the current filters.
              </div>
            ) : (
              filtered.map((c, i) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setParam("id", String(c.id))}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "60px 70px 1.4fr 1.6fr 80px 110px 36px",
                    gap: 10,
                    padding: "10px 14px",
                    width: "100%",
                    alignItems: "center",
                    border: "none",
                    background:
                      selected && selected.id === c.id ? t.panelAlt : "transparent",
                    borderBottom: i < filtered.length - 1 ? `1px solid ${t.borderSoft}` : "none",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: 12.5,
                    color: t.text,
                    fontFamily: t.fontSans,
                  }}
                >
                  <span>
                    <Pill t={t} tone={tierTone(c.tier)} mono>
                      T{c.tier}
                    </Pill>
                  </span>
                  <span style={{ fontFamily: t.fontMono, fontSize: 12.5, color: t.text }}>
                    {c.score.toFixed(1)}
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                    <Mono name={c.name} t={t} size={18} radius={4} />
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      <span style={{ color: t.text, fontWeight: 500 }}>{c.name}</span>
                      {c.industry && (
                        <span style={{ color: t.textMute, marginLeft: 6, fontSize: 11.5 }}>
                          {c.industry}
                        </span>
                      )}
                    </span>
                  </span>
                  <span style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {c.toolsList.length === 0 ? (
                      <span style={{ color: t.textMute, fontSize: 11.5 }}>—</span>
                    ) : (
                      c.toolsList.slice(0, 3).map((tool) => (
                        <Pill key={tool.name} t={t} tone={tool.adoption === "required" ? "accent" : "ghost"}>
                          {tool.name}
                        </Pill>
                      ))
                    )}
                    {c.toolsList.length > 3 && (
                      <span style={{ color: t.textMute, fontSize: 11.5 }}>+{c.toolsList.length - 3}</span>
                    )}
                  </span>
                  <span style={{ fontFamily: t.fontMono, fontSize: 11.5, color: c.openJobs > 0 ? t.text : t.textMute }}>
                    {c.openJobs}
                  </span>
                  <span style={{ fontFamily: t.fontMono, fontSize: 11.5, color: t.textDim }}>
                    {c.lastResearchedAge}
                  </span>
                  <span style={{ color: t.textMute, display: "inline-flex", justifyContent: "flex-end" }}>
                    <icons.chevRight size={11} />
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {selected && <CompanyDrawer t={t} company={selected} onClose={() => setParam("id", null)} />}
    </AppShell>
  );
}

function sort_dir(k: SortKey): 1 | -1 {
  return k === "name" ? 1 : -1;
}

function SortHeader({
  k,
  sort,
  dir,
  t,
  onClick,
  children,
}: {
  k: SortKey;
  sort: SortKey;
  dir: 1 | -1;
  t: ReturnType<typeof beaconTokens>;
  onClick: (k: SortKey) => void;
  children: React.ReactNode;
}) {
  const active = sort === k;
  return (
    <button
      type="button"
      onClick={() => onClick(k)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        background: "transparent",
        border: "none",
        padding: 0,
        cursor: "pointer",
        color: active ? t.text : t.textMute,
        fontSize: 10.5,
        fontFamily: t.fontSans,
        letterSpacing: 0.6,
        textTransform: "uppercase",
        fontWeight: active ? 600 : 500,
      }}
      title={`Sort by ${SORT_LABEL[k]}`}
    >
      {children}
      {active && <span style={{ fontSize: 9 }}>{dir === 1 ? "▲" : "▼"}</span>}
    </button>
  );
}

function DiscoveryRail({ t, discovery }: { t: ReturnType<typeof beaconTokens>; discovery: DiscoveryData }) {
  const [open, setOpen] = useState(true);
  const topCandidates = discovery.candidates.slice(0, 10);
  return (
    <div
      style={{
        background: t.panel,
        border: `1px solid ${t.border}`,
        borderRadius: 6,
        marginBottom: 16,
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: "transparent",
          border: "none",
          borderBottom: open ? `1px solid ${t.borderSoft}` : "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: t.fontSans,
        }}
      >
        <span
          style={{
            fontFamily: t.fontMono,
            fontSize: 10.5,
            color: t.accentInk,
            letterSpacing: 0.6,
            textTransform: "uppercase",
          }}
        >
          Discovery
        </span>
        <Pill t={t} tone="accent" mono>
          {discovery.pendingCount} pending
        </Pill>
        {discovery.sources.map((s) => (
          <span key={s.name} style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textDim }}>
            {s.name}
            <span style={{ color: t.textMute, marginLeft: 4 }}>· {s.pending}</span>
            <span style={{ color: t.textMute, marginLeft: 4 }}>· {s.lastRunAge}</span>
          </span>
        ))}
        <span style={{ flex: 1 }} />
        <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: 10 }}>
          {topCandidates.map((c) => (
            <DiscoveryCandidateRow key={c.id} t={t} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function DiscoveryCandidateRow({ t, c }: { t: ReturnType<typeof beaconTokens>; c: DiscoveryCandidate }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "60px 1fr 90px auto auto",
        gap: 10,
        alignItems: "center",
        padding: "8px 10px",
        background: t.bg,
        border: `1px solid ${t.borderSoft}`,
        borderRadius: 5,
        fontFamily: t.fontSans,
      }}
    >
      <span style={{ fontFamily: t.fontMono, fontSize: 12, color: t.accentInk }}>
        {c.score.toFixed(1)}
      </span>
      <span style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>{c.name}</span>
        <span style={{ fontFamily: t.fontMono, fontSize: 11, color: t.textMute }}>
          {[c.domain, c.hqLocation, c.industry].filter(Boolean).join(" · ") || "—"}
        </span>
      </span>
      <span style={{ display: "inline-flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
        <Pill t={t} tone="ghost" mono>
          {c.source}
        </Pill>
        {c.signalsCount > 0 && (
          <span style={{ fontFamily: t.fontMono, fontSize: 10.5, color: t.textMute }}>
            ★ {c.signalsCount}
          </span>
        )}
      </span>
      <CliMini t={t} command={`beacon companies promote ${c.id} --tier 4`} label="promote" />
      <CliMini t={t} command={`beacon companies reject ${c.id} --reason "..."`} label="reject" />
    </div>
  );
}

function CliMini({ t, command, label }: { t: ReturnType<typeof beaconTokens>; command: string; label: string }) {
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
      title={command}
      style={{
        padding: "4px 8px",
        background: t.panelAlt,
        border: `1px dashed ${t.border}`,
        borderRadius: 4,
        fontFamily: t.fontMono,
        fontSize: 11,
        color: copied ? t.accentInk : t.textDim,
        cursor: "pointer",
        whiteSpace: "nowrap",
      }}
    >
      {copied ? "copied" : label}
    </button>
  );
}

function FilterBar({
  t,
  tier,
  minScore,
  tools,
  allTools,
  setParam,
  toggleTool,
}: {
  t: ReturnType<typeof beaconTokens>;
  tier: number | null;
  minScore: number | null;
  tools: string[];
  allTools: string[];
  setParam: (k: string, v: string | null) => void;
  toggleTool: (n: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>
      <FilterGroup label="Tier" t={t}>
        {[1, 2, 3, 4].map((n) => (
          <ChipButton
            key={n}
            active={tier === n}
            t={t}
            onClick={() => setParam("tier", tier === n ? null : String(n))}
          >
            T{n}
          </ChipButton>
        ))}
        {tier != null && (
          <ChipButton t={t} active={false} onClick={() => setParam("tier", null)} ghost>
            clear
          </ChipButton>
        )}
      </FilterGroup>

      <FilterGroup label="Min score" t={t}>
        {[6, 7, 8, 9].map((n) => (
          <ChipButton
            key={n}
            active={minScore === n}
            t={t}
            onClick={() => setParam("minScore", minScore === n ? null : String(n))}
            mono
          >
            ≥ {n}
          </ChipButton>
        ))}
        {minScore != null && (
          <ChipButton t={t} active={false} onClick={() => setParam("minScore", null)} ghost>
            clear
          </ChipButton>
        )}
      </FilterGroup>

      {allTools.length > 0 && (
        <FilterGroup label="Tools" t={t}>
          {allTools.slice(0, 6).map((name) => (
            <ChipButton
              key={name}
              active={tools.includes(name)}
              t={t}
              onClick={() => toggleTool(name)}
            >
              {name}
            </ChipButton>
          ))}
          {tools.length > 0 && (
            <ChipButton t={t} active={false} onClick={() => setParam("tools", null)} ghost>
              clear
            </ChipButton>
          )}
        </FilterGroup>
      )}
    </div>
  );
}

function FilterGroup({
  label,
  t,
  children,
}: {
  label: string;
  t: ReturnType<typeof beaconTokens>;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
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
      <div style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>{children}</div>
    </div>
  );
}

function ChipButton({
  children,
  active,
  t,
  onClick,
  mono = false,
  ghost = false,
}: {
  children: React.ReactNode;
  active: boolean;
  t: ReturnType<typeof beaconTokens>;
  onClick: () => void;
  mono?: boolean;
  ghost?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "3px 8px",
        borderRadius: 4,
        border: `1px solid ${active ? "transparent" : t.border}`,
        background: active ? t.accentSoft : ghost ? "transparent" : t.panel,
        color: active ? t.accentInk : ghost ? t.textMute : t.textDim,
        fontFamily: mono ? t.fontMono : t.fontSans,
        fontSize: 11.5,
        fontWeight: 500,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function CompanyDrawer({
  t,
  company,
  onClose,
}: {
  t: ReturnType<typeof beaconTokens>;
  company: Company;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.4)",
          zIndex: 30,
        }}
      />
      <aside
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(640px, 92vw)",
          background: t.bg,
          borderLeft: `1px solid ${t.border}`,
          boxShadow: "-12px 0 28px rgba(0,0,0,0.25)",
          zIndex: 31,
          overflowY: "auto",
          fontFamily: t.fontSans,
        }}
      >
        <div
          style={{
            padding: "16px 22px",
            borderBottom: `1px solid ${t.border}`,
            display: "flex",
            alignItems: "center",
            gap: 12,
            position: "sticky",
            top: 0,
            background: t.bg,
            zIndex: 1,
          }}
        >
          <Mono name={company.name} t={t} size={28} radius={6} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 16, fontWeight: 600, color: t.text }}>{company.name}</span>
              <Pill t={t} tone={tierTone(company.tier)} mono>
                T{company.tier}
              </Pill>
              <span style={{ fontFamily: t.fontMono, fontSize: 12, color: t.accentInk }}>
                {company.score.toFixed(1)}
              </span>
            </div>
            <div style={{ fontSize: 12, color: t.textDim, marginTop: 2 }}>
              {[company.industry, company.hqLocation, company.remotePolicy].filter(Boolean).join(" · ") || "—"}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: t.panel,
              border: `1px solid ${t.border}`,
              color: t.textDim,
              padding: "4px 10px",
              borderRadius: 4,
              fontSize: 11,
              cursor: "pointer",
              fontFamily: t.fontMono,
            }}
          >
            esc
          </button>
        </div>

        <div style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: 22 }}>
          {company.description && (
            <p style={{ margin: 0, fontSize: 13.5, color: t.textDim, lineHeight: 1.55 }}>
              {company.description}
            </p>
          )}

          <CliChip t={t} command={`beacon show "${company.name}" --json`} />

          {company.breakdown && (
            <Section t={t} title="Score breakdown">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                }}
              >
                <ScoreRow t={t} label="Leadership" value={company.breakdown.leadership} />
                <ScoreRow t={t} label="Tool adoption" value={company.breakdown.toolAdoption} />
                <ScoreRow t={t} label="Culture" value={company.breakdown.culture} />
                <ScoreRow t={t} label="Evidence depth" value={company.breakdown.evidenceDepth} />
                <ScoreRow t={t} label="Recency" value={company.breakdown.recency} />
                <ScoreRow t={t} label="Composite" value={company.breakdown.composite} highlight />
              </div>
            </Section>
          )}

          {company.toolsList.length > 0 && (
            <Section t={t} title="Tools adopted">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {company.toolsList.map((tool) => (
                  <Pill
                    key={tool.name}
                    t={t}
                    tone={tool.adoption === "required" ? "accent" : "ghost"}
                  >
                    {tool.name}
                    {tool.adoption && (
                      <span style={{ color: t.textMute, marginLeft: 4 }}>· {tool.adoption}</span>
                    )}
                  </Pill>
                ))}
              </div>
            </Section>
          )}

          {company.signals.length > 0 && (
            <Section t={t} title={`AI signals · ${company.signals.length}`}>
              <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 12 }}>
                {company.signals.map((s) => (
                  <li
                    key={s.id}
                    style={{
                      borderLeft: `2px solid ${t.borderSoft}`,
                      paddingLeft: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <Pill t={t} tone="ghost" mono>
                        {s.type}
                      </Pill>
                      {s.dateObserved && (
                        <span style={{ fontFamily: t.fontMono, fontSize: 10.5, color: t.textMute }}>
                          {s.dateObserved}
                        </span>
                      )}
                      {s.strength && (
                        <span style={{ fontFamily: t.fontMono, fontSize: 10.5, color: t.accentInk }}>
                          ★ {s.strength}/5
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: t.text }}>{s.title}</div>
                    {s.excerpt && (
                      <p style={{ margin: "4px 0 0", fontSize: 12.5, color: t.textDim, lineHeight: 1.5 }}>
                        {s.excerpt}
                      </p>
                    )}
                    {s.sourceName && (
                      <div style={{ marginTop: 4, fontSize: 11.5, color: t.textMute, fontFamily: t.fontMono }}>
                        {s.sourceName}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {company.leadership.length > 0 && (
            <Section t={t} title={`Leadership timeline · ${company.leadership.length}`}>
              <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 12 }}>
                {company.leadership.map((l) => (
                  <li
                    key={l.id}
                    style={{
                      borderLeft: `2px solid ${t.borderSoft}`,
                      paddingLeft: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 500, color: t.text }}>{l.leader}</span>
                      {l.title && (
                        <span style={{ fontSize: 11.5, color: t.textMute }}>{l.title}</span>
                      )}
                      {l.dateObserved && (
                        <span style={{ fontFamily: t.fontMono, fontSize: 10.5, color: t.textMute }}>
                          · {l.dateObserved}
                        </span>
                      )}
                    </div>
                    <p style={{ margin: 0, fontSize: 12.5, color: t.textDim, lineHeight: 1.5 }}>
                      “{l.content}”
                    </p>
                    {l.impactLevel && (
                      <div style={{ marginTop: 4, fontSize: 11, color: t.textMute, fontFamily: t.fontMono }}>
                        impact: {l.impactLevel}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          <Section t={t} title="Open in CLI">
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <CliChip t={t} command={`beacon show "${company.name}"`} />
              <CliChip
                t={t}
                command={`beacon jobs --company "${company.name}" --min-relevance 7 --json`}
              />
              <CliChip t={t} command={`beacon scan --company "${company.name}"`} />
            </div>
          </Section>

          {company.careersUrl && (
            <Section t={t} title="Careers">
              <a
                href={company.careersUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12.5,
                  color: t.accentInk,
                  textDecoration: "none",
                }}
              >
                <icons.external size={12} />
                {company.careersUrl}
              </a>
            </Section>
          )}
        </div>
      </aside>
    </>
  );
}

function Section({
  t,
  title,
  children,
}: {
  t: ReturnType<typeof beaconTokens>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: t.fontMono,
          fontSize: 10.5,
          color: t.textMute,
          letterSpacing: 0.6,
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function ScoreRow({
  t,
  label,
  value,
  highlight = false,
}: {
  t: ReturnType<typeof beaconTokens>;
  label: string;
  value: number;
  highlight?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, (value / 10) * 100));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 11.5, color: t.textDim }}>{label}</span>
        <span
          style={{
            fontFamily: t.fontMono,
            fontSize: 12,
            color: highlight ? t.accentInk : t.text,
            fontWeight: highlight ? 600 : 500,
          }}
        >
          {value.toFixed(1)}
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
            background: highlight ? t.accent : t.textMute,
          }}
        />
      </div>
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
        padding: "8px 12px",
        background: t.panelAlt,
        border: `1px dashed ${t.border}`,
        borderRadius: 6,
        cursor: "pointer",
        fontFamily: t.fontMono,
        fontSize: 12,
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
      <span style={{ color: copied ? t.accentInk : t.textMute, fontSize: 11 }}>
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}
