"use client";

import { createContext, useContext } from "react";

import type { ThemeMode } from "../sidebar/Sidebar";

type AppShellContextValue = Readonly<{
  theme: ThemeMode;
  toggleTheme: () => void;
}>;

const AppShellContext = createContext<AppShellContextValue | null>(null);

type AppShellProviderProps = Readonly<{
  children: React.ReactNode;
  value: AppShellContextValue;
}>;

export function AppShellProvider({ children, value }: AppShellProviderProps) {
  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const context = useContext(AppShellContext);

  if (!context) {
    throw new Error("useAppShell must be used within AppShellProvider.");
  }

  return context;
}
