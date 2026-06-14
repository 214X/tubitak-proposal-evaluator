import { FeaturesSection } from "./FeaturesSection";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./homepage.module.css";

export function Homepage() {
  return (
    <main className={styles.main}>
      <div className={styles.backdropOrb} aria-hidden="true" />
      <div className={styles.backdropBeam} aria-hidden="true" />
      <div className={styles.backdropGlow} aria-hidden="true" />

      <div className={styles.themeToggle}>
        <ThemeToggle />
      </div>

      <section className={styles.panel}>
        <div className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.logoWrap}>
              <img
                src="/images/tubitak-logo.png"
                alt="TÜBİTAK logosu"
                className={styles.logo}
              />
            </div>

            <div className={styles.copy}>
              <h1 className={styles.title}>
                Yapay Zeka Destekli Proje Değerlendirme Asistanı
              </h1>
              <p className={styles.description}>
                Proje öneri formunuzu yapay zeka destekli analiz adımlarıyla inceleyin,
                güçlü ve zayıf yönlerini görün ve değerlendirme sürecine daha net
                başlayın.
              </p>
            </div>

            <div className={styles.actions}>
              <a href="/evaluation" className={styles.cta}>
                Değerlendirmeye Başla
              </a>
            </div>
          </div>

          <a href="#how-it-works" className={styles.scrollCue} aria-label="Nasıl çalışır bölümüne git">
            <span className={styles.scrollMouse} aria-hidden="true">
              <span className={styles.scrollWheel} />
            </span>
            <span className={styles.scrollLabel}>Kaydır</span>
          </a>
        </div>

        <FeaturesSection />
      </section>
    </main>
  );
}
