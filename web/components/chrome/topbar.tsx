"use client";

import { Fragment, type ReactNode } from "react";
import type { Tokens } from "@/lib/tokens";
import { Kbd } from "@/components/primitives";
import { icons } from "@/components/icons";

export function Topbar({
  t,
  title,
  subtitle,
  variant = "standard",
  right,
  breadcrumbs,
}: {
  t: Tokens;
  title?: string;
  subtitle?: string;
  variant?: "standard" | "mono";
  right?: ReactNode;
  breadcrumbs?: string[];
}) {
  return (
    <div
      style={{
        height: 48,
        flexShrink: 0,
        borderBottom: `1px solid ${t.border}`,
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "0 16px",
        background: t.bg,
        fontFamily: t.fontSans,
      }}
    >
      {breadcrumbs ? (
        <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13 }}>
          {breadcrumbs.map((b, i) => (
            <Fragment key={i}>
              {i > 0 && (
                <span style={{ color: t.textMute, display: "inline-flex" }}>
                  <icons.chevRight size={11} />
                </span>
              )}
              <span
                style={{
                  color: i === breadcrumbs.length - 1 ? t.text : t.textDim,
                  fontWeight: i === breadcrumbs.length - 1 ? 500 : 400,
                  fontFamily: variant === "mono" ? t.fontMono : t.fontSans,
                }}
              >
                {b}
              </span>
            </Fragment>
          ))}
        </div>
      ) : (
        <>
          {title && <div style={{ fontSize: 13.5, fontWeight: 500, color: t.text }}>{title}</div>}
          {subtitle && (
            <div
              style={{
                fontSize: 12,
                color: t.textDim,
                fontFamily: variant === "mono" ? t.fontMono : t.fontSans,
              }}
            >
              {subtitle}
            </div>
          )}
        </>
      )}
      <div style={{ flex: 1 }} />
      {right}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
          padding: "4px 8px 4px 7px",
          borderRadius: 5,
          border: `1px solid ${t.border}`,
          background: t.panel,
          color: t.textDim,
          fontSize: 12,
          cursor: "pointer",
          minWidth: 180,
        }}
      >
        <span style={{ display: "inline-flex" }}>
          <icons.search size={12} />
        </span>
        <span style={{ flex: 1 }}>Search or run command</span>
        <Kbd t={t}>⌘K</Kbd>
      </div>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          background: "linear-gradient(135deg, oklch(0.74 0.17 145), oklch(0.58 0.17 210))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: 11,
          fontWeight: 600,
          fontFamily: t.fontSans,
        }}
      >
        MP
      </div>
    </div>
  );
}
