import Image from "next/image";
import styles from "./home-hero.module.css";

export function HomeHero() {
  return (
    <section className={styles.hero}>
      <div className={styles.logoContainer}>
        <Image
          src="/images/tubitak-logo.png"
          alt="TÜBİTAK Logo"
          width={3600}
          height={1200}
          className={styles.logo}
          priority
        />
      </div>

      <div className={styles.content}>
        <h1 className={styles.title}>
          TÜBİTAK 1501/1507 programlarına başvuru için{" "}
          <span className={styles.highlightText}>Proje Öneri Bilgileri formu</span>{" "}
          AGY100/AGY101{" "}
          <span className={styles.accentText}>değerlendirme asistanı</span>
        </h1>

        <p className={styles.description}>
          Bu sistem, başvuru dosyanızı yükleyip içeriği hızlı şekilde gözden geçirmeniz,
          formun güçlü ve zayıf yönlerini tek ekranda anlamanız için tasarlandı. Amaç,
          değerlendirme sürecini daha tutarlı, izlenebilir ve pratik hale getirmek.
        </p>
      </div>
    </section>
  );
}

