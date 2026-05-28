"use client";

import { useEffect, useState } from "react";

import { Sidebar, type SidebarSide, type ThemeMode } from "../sidebar/Sidebar";
import styles from "./app-shell.module.css";

type AppShellProps = Readonly<{
  children: React.ReactNode;
}>;

const THEME_STORAGE_KEY = "proposal-evaluator-theme";
const SIDEBAR_SIDE_STORAGE_KEY = "proposal-evaluator-sidebar-side";

export function AppShell({ children }: AppShellProps) {
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [sidebarSide, setSidebarSide] = useState<SidebarSide>("left");

  useEffect(() => {
    const storedTheme = readStorageValue<ThemeMode>(THEME_STORAGE_KEY, ["light", "dark"]);
    const storedSidebarSide = readStorageValue<SidebarSide>(SIDEBAR_SIDE_STORAGE_KEY, [
      "left",
      "right",
    ]);

    if (storedTheme) {
      setTheme(storedTheme);
    }

    if (storedSidebarSide) {
      setSidebarSide(storedSidebarSide);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_SIDE_STORAGE_KEY, sidebarSide);
  }, [sidebarSide]);

  const shellClassName = [
    styles.shell,
    theme === "dark" ? styles.themeDark : "",
    sidebarSide === "right" ? styles.right : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClassName} data-shell data-sidebar-side={sidebarSide}>
      <Sidebar
        theme={theme}
        sidebarSide={sidebarSide}
        onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
        onToggleSidebarSide={() =>
          setSidebarSide((current) => (current === "left" ? "right" : "left"))
        }
      />

      <div className={styles.content} data-content>
        <div className={styles.contentInner}>{children}</div>
      </div>
    </div>
  );
}

function readStorageValue<T extends string>(key: string, acceptedValues: readonly T[]) {
  const value = window.localStorage.getItem(key);
  return acceptedValues.includes(value as T) ? (value as T) : null;
}
