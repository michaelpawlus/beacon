"use client";

import { beaconTokens } from "@/lib/tokens";
import { useTheme } from "@/components/theme-provider";
import { AppShell } from "./app-shell";
import { Topbar } from "./topbar";
import { Kbd } from "@/components/primitives";

export function PlaceholderPage({
  title,
  breadcrumbs,
  cliHint,
  description,
}: {
  title: string;
  breadcrumbs: string[];
  cliHint: string;
  description: string;
}) {
  const { theme } = useTheme();
  const t = beaconTokens(theme);

  return (
    <AppShell>
      <Topbar t={t} breadcrumbs={breadcrumbs} />
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "60px 40px",
          display: "flex",
          justifyContent: "center",
        }}
      >
        <div style={{ maxWidth: 560, width: "100%" }}>
          <div
            style={{
              fontFamily: t.fontMono,
              fontSize: 11,
              letterSpacing: 1,
              color: t.textDim,
              textTransform: "uppercase",
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 500,
              color: t.text,
              letterSpacing: -0.8,
              marginTop: 10,
              lineHeight: 1.2,
            }}
          >
            Not wired up yet.
          </div>
          <div style={{ fontSize: 14, color: t.textDim, marginTop: 14, lineHeight: 1.55 }}>
            {description}
          </div>
          <div
            style={{
              marginTop: 24,
              padding: "14px 16px",
              border: `1px dashed ${t.border}`,
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontFamily: t.fontMono,
              fontSize: 12,
              color: t.textDim,
            }}
          >
            <span style={{ color: t.accentInk }}>$</span>
            <span style={{ color: t.text }}>{cliHint}</span>
            <div style={{ flex: 1 }} />
            <Kbd t={t}>⌘K</Kbd>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
