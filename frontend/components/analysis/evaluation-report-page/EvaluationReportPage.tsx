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
      <EvaluationTopbar />
      <header className={styles.hero}>
        <h1 className={styles.title}>Kriter Bazlı Değerlendirme Raporu</h1>
        <p className={styles.description}>
          Proje önerisinin ana skorlarını, değerlendirme gerekçelerini ve belge kanıtlarını özetler.
        </p>
      </header>
      <EvaluationReportViewer apiBaseUrl={apiBaseUrl} initialSessionId={initialSessionId} />
    </main>
  );
}
