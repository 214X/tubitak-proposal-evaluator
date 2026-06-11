"use client";

import styles from "./analysis-stage-card.module.css";

type StageTone = "idle" | "loading" | "success" | "error" | "waiting";

type AnalysisStageCardProps = Readonly<{
  title: string;
  description: string;
  tone: StageTone;
  details?: React.ReactNode;
  action?: React.ReactNode;
}>;

export function AnalysisStageCard({
  title,
  description,
  tone,
  details,
  action,
}: AnalysisStageCardProps) {
  return (
    <article className={styles.card} data-tone={tone}>
      <div className={styles.header}>
        <div className={styles.statusIcon} data-tone={tone}>
          {tone === "loading" ? <Spinner /> : <StatusDot />}
        </div>

        <div className={styles.headerCopy}>
          <p className={styles.title}>{title}</p>
          <p className={styles.description}>{description}</p>
        </div>

        <span className={styles.statusPill} data-tone={tone}>
          {getToneLabel(tone)}
        </span>
      </div>

      {details ? <div className={styles.details}>{details}</div> : null}
      {action ? <div className={styles.actions}>{action}</div> : null}
    </article>
  );
}

function getToneLabel(tone: StageTone) {
  switch (tone) {
    case "loading":
      return "İşleniyor";
    case "success":
      return "Hazır";
    case "error":
      return "Hata";
    case "waiting":
      return "Bekliyor";
    default:
      return "Hazır Değil";
  }
}

function Spinner() {
  return <span className={styles.spinner} aria-hidden="true" />;
}

function StatusDot() {
  return <span className={styles.dot} aria-hidden="true" />;
}
