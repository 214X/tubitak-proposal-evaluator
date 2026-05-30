import { UploadPanel } from "../../upload-panel/UploadPanel";
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
        <div>
          <p className={styles.eyebrow}>TÜBİTAK PROJE ÖNERİ DEĞERLENDİRME ASİSTANI</p>
        </div>

        <UploadPanel apiBaseUrl={apiBaseUrl} />
      </section>
    </main>
  );
}
