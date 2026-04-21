"use client";

import { useEffect, useState } from "react";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { Sidebar } from "@/components/chrome/sidebar";
import { DashA } from "./dash-a";
import { DashB } from "./dash-b";
import { DashC } from "./dash-c";
import type { BeaconData } from "@/lib/types";

export type Direction = "a" | "b" | "c";

const DIRECTIONS: Array<{ k: Direction; label: string; caption: string }> = [
  { k: "a", label: "A · Command Deck", caption: "Linear-dense, accent on signals" },
  { k: "b", label: "B · Briefing", caption: "Editorial reading column" },
  { k: "c", label: "C · Console", caption: "Mono-tinged, CLI-peer" },
];

export function DashboardWithToggle({ data }: { data: BeaconData }) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);
  const [direction, setDirection] = useState<Direction>("a");

  useEffect(() => {
    const stored = localStorage.getItem("beacon-direction") as Direction | null;
    if (stored === "a" || stored === "b" || stored === "c") setDirection(stored);
  }, []);

  const pick = (d: Direction) => {
    setDirection(d);
    try {
      localStorage.setItem("beacon-direction", d);
    } catch {
      // ignore
    }
  };

  const sidebarVariant = direction === "c" ? "mono" : "standard";

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        background: t.bg,
        color: t.text,
        fontFamily: t.fontSans,
        overflow: "hidden",
      }}
    >
      <Sidebar t={t} variant={sidebarVariant} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, position: "relative" }}>
        {/* direction picker — floats top-left of content area */}
        <div
          style={{
            position: "absolute",
            top: 10,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 40,
            display: "inline-flex",
            gap: 1,
            padding: 3,
            background: t.panelAlt,
            border: `1px solid ${t.border}`,
            borderRadius: 7,
            boxShadow: "0 2px 12px rgba(0,0,0,0.15)",
          }}
        >
          {DIRECTIONS.map((d) => {
            const active = direction === d.k;
            return (
              <button
                key={d.k}
                title={d.caption}
                onClick={() => pick(d.k)}
                style={{
                  border: "none",
                  background: active ? t.panel : "transparent",
                  color: active ? t.text : t.textDim,
                  padding: "4px 10px",
                  fontSize: 11.5,
                  fontFamily: t.fontSans,
                  fontWeight: 500,
                  borderRadius: 5,
                  cursor: "pointer",
                  letterSpacing: -0.1,
                }}
              >
                {d.label}
              </button>
            );
          })}
        </div>

        {direction === "a" && <DashA t={t} data={data} />}
        {direction === "b" && <DashB t={t} data={data} />}
        {direction === "c" && <DashC t={t} data={data} />}
      </div>
    </div>
  );
}
