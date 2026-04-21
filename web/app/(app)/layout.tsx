import type { ReactNode } from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/chrome/theme-toggle";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <ThemeToggle />
      {children}
    </ThemeProvider>
  );
}
