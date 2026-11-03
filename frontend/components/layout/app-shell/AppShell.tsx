"use client";

import { useEffect, useState } from "react";
import { flushSync } from "react-dom";

import { AppShellProvider } from "./AppShellContext";
import type { ThemeMode } from "../sidebar/Sidebar";
import styles from "./app-shell.module.css";

type AppShellProps = Readonly<{
  children: React.ReactNode;
}>;

const THEME_STORAGE_KEY = "proposal-evaluator-theme";

type DocumentWithViewTransition = Document & {
  startViewTransition?: (callback: () => void) => void;
};

export function AppShell({ children }: AppShellProps) {
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    const storedTheme = readStorageValue<ThemeMode>(THEME_STORAGE_KEY, ["light", "dark"]);

    if (storedTheme) {
      setTheme(storedTheme);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    // data-theme'i <html>'e de yaz; böylece document.body'ye portallanan
    // modaller (rubric / alt kriter detayı) doğru token setini miras alır.
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const shellClassName = [styles.shell, theme === "dark" ? styles.themeDark : ""]
    .filter(Boolean)
    .join(" ");

  function runWithViewTransition(update: () => void) {
    const documentWithTransition = document as DocumentWithViewTransition;

    if (!documentWithTransition.startViewTransition) {
      update();
      return;
    }

    documentWithTransition.startViewTransition(() => {
      flushSync(update);
    });
  }

  const toggleTheme = () =>
    runWithViewTransition(() =>
      setTheme((current) => (current === "light" ? "dark" : "light")),
    );

  return (
    <AppShellProvider value={{ theme, toggleTheme }}>
      <div className={shellClassName} data-shell data-theme={theme}>
        <div className={styles.content} data-content>
          <div className={styles.contentInner}>{children}</div>
        </div>
      </div>
    </AppShellProvider>
  );
}

function readStorageValue<T extends string>(key: string, acceptedValues: readonly T[]) {
  const value = window.localStorage.getItem(key);
  return acceptedValues.includes(value as T) ? (value as T) : null;
}
