import styles from "./features-section.module.css";

const FEATURES = [
  {
    step: "1",
    title: "Belgeyi Yapısal Olarak Okur",
    description:
      "Sistem proje öneri formunu yalnızca düz metin olarak ele almaz; başlıkları, alt bölümleri, tabloları ve belge içindeki ilişkili alanları ayrıştırarak okunabilir bir yapı oluşturur.",
    highlight: "Dağınık içerik yerine tutarlı bir belge haritası çıkarılır.",
    icon: <StructureIcon />,
  },
  {
    step: "2",
    title: "İçeriği Anlamlandırır",
    description:
      "Teknik anlatım, problem tanımı, çözüm yaklaşımı, iş planı ve beklenen çıktıların birbiriyle ne kadar uyumlu olduğu yapay zeka destekli analiz katmanlarında incelenir.",
    highlight: "Metnin yalnızca ne söylediği değil, nasıl kurgulandığı da değerlendirilir.",
    icon: <SparkIcon />,
  },
  {
    step: "3",
    title: "Güçlü ve Zayıf Noktaları Ayıklar",
    description:
      "Açık anlatılmış bölümler, eksik bırakılmış noktalar, belirsiz ifadeler ve ikna gücünü düşüren alanlar ayrıştırılarak kullanıcıya anlaşılır bir çerçevede sunulur.",
    highlight: "Karar vericinin dikkat edeceği kırılgan alanlar daha görünür hale gelir.",
    icon: <ReportIcon />,
  },
  {
    step: "4",
    title: "Raporu Eyleme Dönüştürür",
    description:
      "Çıktılar yalnızca tespit listesi olarak bırakılmaz; kullanıcıya üzerinde çalışabileceği net bir değerlendirme özeti ve rapor akışı halinde sunulur.",
    highlight: "Böylece değerlendirme ekranı, belgeyi yeniden güçlendirmek için doğrudan kullanılabilir bir çalışma alanına dönüşür.",
    icon: <RouteIcon />,
  },
] as const;

export function FeaturesSection() {
  return (
    <section
      id="how-it-works"
      className={styles.section}
      aria-labelledby="homepage-features-title"
    >
      <div className={styles.header}>
        <p className={styles.eyebrow}>Nasıl çalışır</p>
        <h2 id="homepage-features-title" className={styles.title}>
          Belgeden rapora uzanan değerlendirme akışı
        </h2>
        <p className={styles.intro}>
          Ana sayfa ürünü tanıtır; gerçek çalışma Evaluation ekranında başlar. Aşağıdaki
          akış, sistemin proje önerinizi nasıl okuyup anlamlandırdığını ve çıktıya nasıl
          dönüştürdüğünü özetler.
        </p>
      </div>

      <div className={styles.list}>
        {FEATURES.map((feature) => (
          <article key={feature.title} className={styles.item}>
            <div className={styles.rail} aria-hidden="true">
              <div className={styles.stepBadge}>{feature.step}</div>
              <div className={styles.railLine} />
            </div>

            <div className={styles.card}>
              <div className={styles.cardTop}>
                <div className={styles.iconWrap} aria-hidden="true">
                  {feature.icon}
                </div>
                <p className={styles.mobileStep}>{feature.step}</p>
              </div>

              <div className={styles.itemCopy}>
                <h3 className={styles.itemTitle}>{feature.title}</h3>
                <p className={styles.itemDescription}>{feature.description}</p>
                <p className={styles.itemHighlight}>{feature.highlight}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function StructureIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M5 5.5h14" />
      <path d="M5 10h14" />
      <path d="M5 14.5h6" />
      <path d="M5 19h6" />
      <rect x="13.5" y="13.5" width="5.5" height="5.5" rx="1.2" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 3.5 14.2 9l5.8 2.2-5.8 2.2L12 19l-2.2-5.6L4 11.2 9.8 9 12 3.5Z" />
    </svg>
  );
}

function ReportIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1Z" />
      <path d="M14 3.5V8h4" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </svg>
  );
}

function RouteIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M5 18.5a2.5 2.5 0 1 0 0-5h8a2.5 2.5 0 1 1 0-5h6" />
      <path d="M17 4.5h2v2" />
      <path d="M5 18.5h2" />
    </svg>
  );
}
