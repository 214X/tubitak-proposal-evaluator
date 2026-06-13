"use client";

import styles from "./analyze-button.module.css";

type AnalyzeButtonProps = Readonly<{
  disabled?: boolean;
  isBusy?: boolean;
  onClick?: () => void;
  helperText?: string;
  passive?: boolean;
  mode?: "full" | "chunk_only";
}>;

export function AnalyzeButton({
  disabled = false,
  isBusy = false,
  onClick,
  helperText,
  passive = false,
  mode = "full",
}: AnalyzeButtonProps) {
  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.button}
        onClick={onClick}
        disabled={disabled || passive}
      >
        <span className={styles.buttonIcon}>
          <SparkIcon />
        </span>
        <span className={styles.buttonCopy}>
          <span className={styles.buttonTitle}>
            {isBusy
              ? "Analiz İşleniyor"
              : mode === "chunk_only"
                ? "Chunking'e Kadar Çalıştır"
                : "Belgeyi Analize Başla"}
          </span>
          <span className={styles.buttonDescription}>
            {passive
              ? "Bu aksiyon şimdilik debug akışında aktif."
              : mode === "chunk_only"
                ? "Extraction, parser ve chunking aşamalarını çalıştırır; embedding başlatmaz."
                : "Extraction, parser, chunking ve embedding aşamalarını arka planda çalıştırır."}
          </span>
        </span>
      </button>

      {helperText ? <p className={styles.helperText}>{helperText}</p> : null}
    </div>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z" />
      <path d="m18.5 2.5.7 1.8L21 5l-1.8.7-.7 1.8-.7-1.8L16 5l1.8-.7.7-1.8Z" />
      <path d="m5.5 16.5.7 1.8L8 19l-1.8.7-.7 1.8-.7-1.8L3 19l1.8-.7.7-1.8Z" />
    </svg>
  );
}
