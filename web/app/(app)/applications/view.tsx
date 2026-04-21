"use client";

import { useEffect, useState } from "react";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "@/components/chrome/app-shell";
import { Topbar } from "@/components/chrome/topbar";
import { PipelineKanban } from "./pipeline-kanban";
import { PipelineList } from "./pipeline-list";
import type { BeaconData } from "@/lib/types";

type View = "kanban" | "list";

export function ApplicationsView({ data }: { data: BeaconData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);
  const [view, setView] = useState<View>("kanban");

  useEffect(() => {
    const stored = localStorage.getItem("beacon-pipeline-view") as View | null;
    if (stored === "kanban" || stored === "list") setView(stored);
  }, []);

  const pick = (v: View) => {
    setView(v);
    try {
      localStorage.setItem("beacon-pipeline-view", v);
    } catch {
      // ignore
    }
  };

  return (
    <AppShell>
      <Topbar
        t={t}
        breadcrumbs={["Applications"]}
        right={
          <div
            style={{
              display: "inline-flex",
              gap: 1,
              padding: 3,
              background: t.panelAlt,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
            }}
          >
            {(["kanban", "list"] as const).map((v) => {
              const active = view === v;
              return (
                <button
                  key={v}
                  onClick={() => pick(v)}
                  style={{
                    border: "none",
                    background: active ? t.panel : "transparent",
                    color: active ? t.text : t.textDim,
                    padding: "3px 10px",
                    fontSize: 11.5,
                    fontFamily: t.fontSans,
                    fontWeight: 500,
                    borderRadius: 4,
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {v}
                </button>
              );
            })}
          </div>
        }
      />
      {view === "kanban" ? <PipelineKanban t={t} data={data} /> : <PipelineList t={t} data={data} />}
    </AppShell>
  );
}
