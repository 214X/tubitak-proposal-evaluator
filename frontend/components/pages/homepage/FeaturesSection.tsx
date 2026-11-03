import styles from "./features-section.module.css";

const FEATURES = [
  {
    step: "1",
    title: "Proje Önerinizi Baştan Sona Okur",
    description:
      "Hazırladığınız proje öneri formunu PDF olarak yüklemeniz yeterli. Sistem belgeyi bütün olarak okur; başlıkları, alt bölümleri, tabloları ve birbirine bağlı kısımları tek tek tarar. Hiçbir sayfayı atlamaz, hiçbir bölümü gözden kaçırmaz.",
    highlight: "Formunuzun tamamı, dağınık metin yığını değil; düzenli bir bütün olarak ele alınır.",
    icon: <StructureIcon />,
  },
  {
    step: "2",
    title: "Söylediklerinizi Anlamaya Çalışır",
    description:
      "Projenizin amacı, çözmek istediği problem, izlediği yöntem, iş planı ve beklenen sonuçlar birbiriyle ne kadar tutarlı, ne kadar inandırıcı? Sistem bu soruların yanıtını yalnızca belgenizdeki ifadelere bakarak arar; dışarıdan bilgi eklemez, varsayımda bulunmaz.",
    highlight: "Yorumların hepsi sizin yazdıklarınıza dayanır; uydurma veya tahmin yoktur.",
    icon: <SparkIcon />,
  },
  {
    step: "3",
    title: "Güçlü ve Zayıf Yönleri Tek Tek Çıkarır",
    description:
      "İyi anlatılmış bölümler, eksik bırakılan noktalar, belirsiz kalan ifadeler ve değerlendirmede sizi zorlayabilecek yerler ayrı ayrı listelenir. Her tespitin yanında, bunu belgenizin hangi cümlesine dayandırdığı da gösterilir.",
    highlight: "Neyin güçlü, neyin zayıf olduğunu ve bunun nedenini açıkça görürsünüz.",
    icon: <ReportIcon />,
  },
  {
    step: "4",
    title: "Anlaşılır Bir Puan ve Rapora Dönüştürür",
    description:
      "Her kriter için bir puan, her puanın arkasında \"neden bu puan?\" açıklaması ve tüm önerinin genel değerlendirmesi tek bir raporda toplanır. Raporu ekranda inceleyebilir, PDF olarak indirebilir veya e-posta ile paylaşabilirsiniz.",
    highlight: "Sonuç, başvurunuzu göndermeden önce eksiklerinizi görüp düzeltebileceğiniz net bir yol haritasıdır.",
    icon: <RouteIcon />,
  },
] as const;

const DIMENSIONS = [
  {
    badge: "A",
    weight: "%45",
    title: "Ar-Ge ve Yenilikçilik",
    description:
      "Projenizin gerçekten yeni bir teknik problemi çözüp çözmediğine, hedeflediği teknoloji düzeyine ve yenilikçi yönüne bakar. Değerlendirmede en yüksek ağırlığa sahip, yani en belirleyici boyut budur.",
  },
  {
    badge: "B",
    weight: "%30",
    title: "Plan, Ekip ve Altyapı",
    description:
      "Projenin uygulanabilir bir iş planıyla, işin altından kalkabilecek bir ekiple ve yeterli kurumsal imkânlarla gerçekten yürütülebilir olup olmadığını inceler.",
  },
  {
    badge: "C",
    weight: "%25",
    title: "Ekonomik ve Ulusal Katkı",
    description:
      "Proje çıktılarının pazarda karşılık bulma, ekonomik fayda üretme ve ülkeye kazanım sağlama potansiyelini değerlendirir.",
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
          Proje önerinizi yüklemekten rapora dört adım
        </h2>
        <p className={styles.intro}>
          Bu asistan, TÜBİTAK 1501 ve 1507 sanayi Ar-Ge destek programlarına hazırlanan
          proje önerilerini değerlendirmek için tasarlandı. Başvurunuzu göndermeden önce
          güçlü ve zayıf yönlerinizi görmenizi, eksiklerinizi fark etmenizi sağlar.
          Aşağıda, yüklediğiniz belgenin nasıl bir değerlendirmeye dönüştüğünü adım adım
          görebilirsiniz.
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

      <div className={styles.scope}>
        <div className={styles.header}>
          <p className={styles.eyebrow}>Neyi değerlendirir</p>
          <h2 className={styles.title}>Önerinizi üç temel boyutta inceler</h2>
          <p className={styles.intro}>
            Bir hakemin proje önerinize bakarken sorduğu temel sorular üç ana başlıkta
            toplanır. Sistem de aynı çerçeveyi kullanır: her boyut kendi alt başlıklarına
            ayrılır ve her biri, belgenizden bulduğu kanıtlara dayanarak ayrı ayrı puanlanır.
          </p>
        </div>

        <div className={styles.dimensionGrid}>
          {DIMENSIONS.map((dimension) => (
            <article key={dimension.badge} className={styles.dimensionCard}>
              <div className={styles.dimensionTop}>
                <span className={styles.dimensionBadge}>{dimension.badge}</span>
                <span className={styles.weightChip}>{dimension.weight} ağırlık</span>
              </div>
              <h3 className={styles.dimensionTitle}>{dimension.title}</h3>
              <p className={styles.dimensionText}>{dimension.description}</p>
            </article>
          ))}
        </div>

        <p className={styles.scopeNote}>
          Bu boyutların toplam ağırlığı genel puanınızı oluşturur. Böylece projenizin hangi
          alanda öne çıktığını, hangi alanda güçlenmesi gerektiğini tek bakışta görürsünüz.
        </p>
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
