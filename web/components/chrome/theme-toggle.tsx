"use client";

import { useTheme } from "@/components/theme-provider";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div
      style={{
        position: "fixed",
        top: 14,
        right: 14,
        zIndex: 50,
        display: "inline-flex",
        background: "rgba(18,14,10,0.85)",
        backdropFilter: "blur(10px)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 7,
        padding: 3,
        gap: 1,
        fontFamily: '"Geist", system-ui, sans-serif',
      }}
    >
      {(["dark", "light"] as const).map((option) => {
        const active = theme === option;
        return (
          <button
            key={option}
            onClick={() => setTheme(option)}
            style={{
              border: "none",
              background: active ? "rgba(255,255,255,0.12)" : "transparent",
              color: active ? "#fff" : "rgba(255,255,255,0.55)",
              padding: "5px 12px",
              fontSize: 12,
              fontWeight: 500,
              borderRadius: 5,
              cursor: "pointer",
              letterSpacing: -0.1,
              textTransform: "capitalize",
            }}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
