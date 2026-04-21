"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Tokens } from "@/lib/tokens";
import { Kbd } from "@/components/primitives";
import { icons } from "@/components/icons";
import type { IconName } from "@/components/icons";

type NavItem = {
  k: string;
  label: string;
  icon: IconName;
  shortcut: string;
  badge: number | null;
  href: string;
};

const NAV: NavItem[] = [
  { k: "dash",     label: "Dashboard",    icon: "dashboard", shortcut: "G D", badge: null, href: "/dashboard" },
  { k: "jobs",     label: "Jobs",         icon: "jobs",      shortcut: "G J", badge: 12,   href: "/jobs" },
  { k: "comp",     label: "Companies",    icon: "companies", shortcut: "G C", badge: null, href: "/companies" },
  { k: "apps",     label: "Applications", icon: "apps",      shortcut: "G A", badge: 4,    href: "/applications" },
  { k: "content",  label: "Content",      icon: "content",   shortcut: "G O", badge: null, href: "/content" },
  { k: "settings", label: "Settings",     icon: "settings",  shortcut: "G S", badge: null, href: "/settings" },
];

export function Sidebar({ t, variant = "standard" }: { t: Tokens; variant?: "standard" | "mono" }) {
  const pathname = usePathname();
  const labelFont = variant === "mono" ? t.fontMono : t.fontSans;

  return (
    <div
      style={{
        width: 220,
        flexShrink: 0,
        height: "100%",
        background: t.bg,
        borderRight: `1px solid ${t.border}`,
        display: "flex",
        flexDirection: "column",
        fontFamily: t.fontSans,
      }}
    >
      <div style={{ padding: "16px 16px 14px", display: "flex", alignItems: "center", gap: 9 }}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 5,
            background: t.text,
            color: t.bg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: t.fontMono,
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: -0.5,
          }}
        >
          B
        </div>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: t.text, letterSpacing: -0.2 }}>beacon</div>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: t.fontMono, fontSize: 10, color: t.textMute }}>v0.4</span>
      </div>

      <div style={{ padding: "0 8px 10px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 8px",
            borderRadius: 6,
            background: t.panelAlt,
            border: `1px solid ${t.borderSoft}`,
            fontSize: 12,
            color: t.textDim,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 3, background: t.accent }} />
          <span style={{ flex: 1, color: t.text, fontWeight: 500 }}>AI-native search</span>
          <Kbd t={t}>⌘K</Kbd>
        </div>
      </div>

      <div style={{ padding: "4px 8px", flex: 1, display: "flex", flexDirection: "column", gap: 1 }}>
        {NAV.map((n) => {
          const isActive = pathname === n.href || (n.href !== "/dashboard" && pathname.startsWith(n.href));
          const Icon = icons[n.icon];
          return (
            <Link key={n.k} href={n.href} style={{ textDecoration: "none" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "6px 8px",
                  borderRadius: 5,
                  background: isActive ? t.panelAlt : "transparent",
                  color: isActive ? t.text : t.textDim,
                  fontFamily: labelFont,
                  fontSize: 13,
                  fontWeight: isActive ? 500 : 400,
                  cursor: "pointer",
                }}
              >
                <span style={{ color: isActive ? t.text : t.textMute, display: "inline-flex" }}>
                  <Icon size={14} />
                </span>
                <span style={{ flex: 1 }}>{n.label}</span>
                {n.badge != null && (
                  <span
                    style={{
                      fontFamily: t.fontMono,
                      fontSize: 10,
                      fontWeight: 500,
                      color: t.textDim,
                      background: t.bg,
                      border: `1px solid ${t.border}`,
                      padding: "1px 5px",
                      borderRadius: 3,
                    }}
                  >
                    {n.badge}
                  </span>
                )}
              </div>
            </Link>
          );
        })}
      </div>

      <div style={{ padding: "8px 12px 12px", borderTop: `1px solid ${t.borderSoft}` }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontFamily: t.fontMono,
            fontSize: 10.5,
            color: t.textMute,
            letterSpacing: 0.2,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 3,
              background: t.accent,
              boxShadow: `0 0 6px ${t.accent}`,
            }}
          />
          <span style={{ color: t.textDim }}>cli synced</span>
          <span style={{ flex: 1 }} />
          <span>2m</span>
        </div>
      </div>
    </div>
  );
}
