import { EvaluationReportViewer } from "../evaluation-panel/EvaluationPanel";
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
      <EvaluationReportViewer apiBaseUrl={apiBaseUrl} initialSessionId={initialSessionId} />
    </main>
  );
}
