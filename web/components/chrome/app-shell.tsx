"use client";

import type { ReactNode } from "react";
import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { Sidebar } from "./sidebar";

export function AppShell({
  children,
  sidebarVariant = "standard",
}: {
  children: ReactNode;
  sidebarVariant?: "standard" | "mono";
}) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);
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
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>{children}</div>
    </div>
  );
}
