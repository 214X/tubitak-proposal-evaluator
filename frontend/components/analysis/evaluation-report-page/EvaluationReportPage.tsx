import { EvaluationReportViewer } from "../evaluation-panel/EvaluationPanel";
import { EvaluationTopbar } from "../../pages/evaluation/EvaluationTopbar";
import styles from "./evaluation-report-page.module.css";

type EvaluationReportPageProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

export function EvaluationReportPage({
  apiBaseUrl,
  initialSessionId = null,
}: EvaluationReportPageProps) {
  return (
    <main className={styles.page}>
      <div className={styles.backdropOrb} aria-hidden="true" />
      <div className={styles.backdropBeam} aria-hidden="true" />
      <div className={styles.backdropGlow} aria-hidden="true" />
      <EvaluationTopbar />
      <EvaluationReportViewer apiBaseUrl={apiBaseUrl} initialSessionId={initialSessionId} />
    </main>
  );
}
