import { UploadPanel } from "../../upload-panel/UploadPanel";
import styles from "./homepage.module.css";

type HomepageProps = Readonly<{
  health: {
    status: string;
    service: string;
    version: string;
  };
  apiBaseUrl: string;
}>;

export function Homepage({ health, apiBaseUrl }: HomepageProps) {
  return (
    <main className={styles.main}>
      <section className={styles.panel}>
        <div>
          <p className={styles.eyebrow}>TUBITAK PROPOSAL EVALUATOR</p>
        </div>

        <UploadPanel apiBaseUrl={apiBaseUrl} />
      </section>
    </main>
  );
}
