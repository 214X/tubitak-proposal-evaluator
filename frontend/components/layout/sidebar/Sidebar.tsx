"use client";

import { useState } from "react";

import styles from "./sidebar.module.css";

export type ThemeMode = "light" | "dark";
export type SidebarSide = "left" | "right";

type SidebarProps = Readonly<{
  theme: ThemeMode;
  sidebarSide: SidebarSide;
  onToggleTheme: () => void;
  onToggleSidebarSide: () => void;
}>;

export function Sidebar({
  theme,
  sidebarSide,
  onToggleTheme,
  onToggleSidebarSide,
}: SidebarProps) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <aside className={styles.sidebar} data-sidebar>
      <div className={styles.sidebarInner}>
        <div className={styles.brandRow}>
          <div className={styles.brandMark}>
            <FlaskIcon />
          </div>
          <div className={styles.brandCopy}>
            <p className={styles.brandTitle}>TUBİTAK Proje Önerisi Değerlendirme</p>
          </div>
        </div>

        <div className={styles.divider} />

        <nav className={styles.navGroup} aria-label="Primary navigation">
          <button type="button" className={`${styles.navButton} ${styles.navButtonActive}`}>
            <span className={styles.navIcon}>
              <HomeIcon />
            </span>
            <span className={styles.navText}>
              <span className={styles.navTitle}>Ana Sayfa</span>
            </span>
          </button>

          <button type="button" className={styles.navButton}>
            <span className={styles.navIcon}>
              <LayersIcon />
            </span>
            <span className={styles.navText}>
              <span className={styles.navTitle}>Debug Akışı</span>
            </span>
          </button>
        </nav>

        <section className={styles.settingsPanel} aria-label="Settings">
          <button
            type="button"
            className={`${styles.navButton} ${styles.settingsToggle} ${
              isSettingsOpen ? styles.navButtonActive : ""
            }`}
            onClick={() => setIsSettingsOpen((current) => !current)}
            aria-expanded={isSettingsOpen}
          >
            <span className={styles.settingLeft}>
              <span className={styles.navIcon}>
                <SettingsIcon />
              </span>
              <span className={styles.navText}>
                <span className={styles.navTitle}>Settings</span>
              </span>
            </span>
            <span
              className={`${styles.chevron} ${isSettingsOpen ? styles.chevronOpen : ""}`}
              aria-hidden="true"
            >
              <ChevronIcon />
            </span>
          </button>

          {isSettingsOpen ? (
            <div className={styles.settingsBody}>
              <button type="button" className={styles.settingButton} onClick={onToggleTheme}>
                <span className={styles.settingLeft}>
                  <span className={styles.settingIcon}>
                    {theme === "light" ? <SunIcon /> : <MoonIcon />}
                  </span>
                  <span className={styles.settingLabel}>
                    <span className={styles.settingTitle}>Theme</span>
                  </span>
                </span>
                <span className={styles.settingsHint}>{theme === "light" ? "Güneş" : "Ay"}</span>
              </button>

              <button
                type="button"
                className={styles.settingButton}
                onClick={onToggleSidebarSide}
              >
                <span className={styles.settingLeft}>
                  <span className={styles.settingIcon}>
                    <SwapSideIcon direction={sidebarSide} />
                  </span>
                  <span className={styles.settingLabel}>
                    <span className={styles.settingTitle}>Sidebar Position</span>
                  </span>
                </span>
                <span className={styles.settingsHint}>
                  {sidebarSide === "left" ? "Sağa al" : "Sola al"}
                </span>
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </aside>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5v10a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-10" />
      <path d="M9.5 20.5v-6h5v6" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z" />
      <path d="m4 12 8 4.5 8-4.5" />
      <path d="m4 16.5 8 4.5 8-4.5" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 2.8 1.2 2.1 2.4.4.8 2.3 2.2 1-.3 2.4 1.6 1.8-1.6 1.8.3 2.4-2.2 1-.8 2.3-2.4.4L12 21.2l-1.2-2.1-2.4-.4-.8-2.3-2.2-1 .3-2.4-1.6-1.8 1.6-1.8-.3-2.4 2.2-1 .8-2.3 2.4-.4L12 2.8Z" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.5v2.7M12 18.8v2.7M21.5 12h-2.7M5.2 12H2.5M18.7 5.3l-1.9 1.9M7.2 16.8l-1.9 1.9M18.7 18.7l-1.9-1.9M7.2 7.2 5.3 5.3" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 14.2A8.5 8.5 0 1 1 9.8 4a7 7 0 0 0 10.2 10.2Z" />
    </svg>
  );
}

function SwapSideIcon({ direction }: { direction: SidebarSide }) {
  return direction === "left" ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M10 5v14" />
      <path d="m14.5 12 3-3m-3 3 3 3" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M14 5v14" />
      <path d="m9.5 12-3-3m3 3-3 3" />
    </svg>
  );
}

function FlaskIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10 2.8h4" />
      <path d="M10.8 2.8v5.1L5.7 17.1a3.3 3.3 0 0 0 2.9 4.9h6.8a3.3 3.3 0 0 0 2.9-4.9l-5.1-9.2V2.8" />
      <path d="M8.3 14.2h7.4" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
