import { DebugFlowWorkspace } from "./DebugFlowWorkspace";
import styles from "./debug-flow.module.css";

type DebugFlowPageProps = Readonly<{
  health: {
    status: string;
    service: string;
    version: string;
  };
  apiBaseUrl: string;
}>;

export function DebugFlowPage({ health, apiBaseUrl }: DebugFlowPageProps) {
  return (
    <main className={styles.main}>
      <section className={styles.panel}>
        <div className={styles.headerBlock}>
          <p className={styles.eyebrow}>TÜBİTAK PROJE ÖNERİ DEĞERLENDİRME ASİSTANI</p>
          <h1 className={styles.title}>Debug Analiz Akışı</h1>
          <p className={styles.description}>
            Upload, extraction, parser ve arka plan analysis durumunu bu sayfadan
            izleyin.
          </p>
        </div>

        <DebugFlowWorkspace apiBaseUrl={apiBaseUrl} />
      </section>
    </main>
  );
}
