import { EvaluationTopbar } from "./EvaluationTopbar";
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
      <div className={styles.backdropOrb} aria-hidden="true" />
      <div className={styles.backdropBeam} aria-hidden="true" />
      <div className={styles.backdropGlow} aria-hidden="true" />

      <EvaluationTopbar />
      <section className={styles.panel}>
        <div className={styles.headerBlock}>
          <p className={styles.eyebrow}>TÜBİTAK PROJE ÖNERİ DEĞERLENDİRME ASİSTANI</p>
          <h1 className={styles.title}>Rapor Değerlendirme Alanı</h1>
          <p className={styles.description}>
            Belgenizi yükleyin, yapay zeka destekli analiz adımlarını takip edin ve
            kapsamlı TÜBİTAK değerlendirme raporunuza ulaşın.
          </p>
        </div>

        <EvaluationWorkspace apiBaseUrl={apiBaseUrl} />
      </section>
    </main>
  );
}
