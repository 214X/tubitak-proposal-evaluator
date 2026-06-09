import { HomeHero } from "../../home-hero/HomeHero";
import { AnalyzeButton } from "../../analysis/analyze-button/AnalyzeButton";
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
        <HomeHero />
        <UploadPanel apiBaseUrl={apiBaseUrl} />
        <div className={styles.analysisEntry}>
          <AnalyzeButton
            passive
            helperText="Bu kontrol şimdilik sadece Debug Akışı ekranında gerçek işlev kazanır."
          />
        </div>
      </section>
    </main>
  );
}
