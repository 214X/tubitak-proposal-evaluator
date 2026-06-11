import { EvaluationWorkspace } from "./EvaluationWorkspace";
import styles from "./evaluation-page.module.css";

type EvaluationPageProps = Readonly<{
  health: {
    status: string;
    service: string;
    version: string;
  };
  apiBaseUrl: string;
}>;

export function EvaluationPage({ health, apiBaseUrl }: EvaluationPageProps) {
  return (
    <main className={styles.main}>
      <section className={styles.panel}>
        <div className={styles.headerBlock}>
          <p className={styles.eyebrow}>TÜBİTAK PROJE ÖNERİ DEĞERLENDİRME ASİSTANI</p>
          <h1 className={styles.title}>Evaluation Workspace</h1>
          <p className={styles.description}>
            Ayrı evaluation akışını bu sayfadan başlatın, ilerleme aşamalarını takip edin ve
            tamamlandığında raporu yeni sekmede açın.
          </p>
          <p className={styles.health}>
            API: {health.status} • {health.service}
          </p>
        </div>

        <EvaluationWorkspace apiBaseUrl={apiBaseUrl} />
      </section>
    </main>
  );
}
