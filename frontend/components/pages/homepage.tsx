type HomepageProps = {
  health: {
    status: string;
    service: string;
    version: string;
  };
};

export function Homepage({ health }: HomepageProps) {
  const isHealthy = health.status === "ok";

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "24px",
      }}
    >
      <section
        style={{
          width: "100%",
          maxWidth: "720px",
          padding: "40px",
          borderRadius: "24px",
          background: "rgba(255, 255, 255, 0.88)",
          border: "1px solid rgba(20, 33, 61, 0.08)",
          boxShadow: "0 24px 80px rgba(20, 33, 61, 0.12)",
          backdropFilter: "blur(10px)",
        }}
      >
        <p
          style={{
            margin: "0 0 12px",
            fontSize: "14px",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "#5c677d",
          }}
        >
          TUBITAK Proposal Evaluator
        </p>
        <h1
          style={{
            margin: "0 0 16px",
            fontSize: "40px",
            lineHeight: 1.1,
          }}
        >
          Platform health checkpoint
        </h1>
        <p
          style={{
            margin: "0 0 32px",
            fontSize: "18px",
            color: "#33415c",
          }}
        >
          Frontend ana sayfası backend health endpoint sonucunu gösterir.
        </p>

        <div
          style={{
            display: "grid",
            gap: "16px",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          }}
        >
          <MetricCard
            label="Status"
            value={health.status}
            accent={isHealthy ? "#2a9d8f" : "#e76f51"}
          />
          <MetricCard
            label="Service"
            value={health.service}
            accent="#3772ff"
          />
          <MetricCard
            label="Version"
            value={health.version}
            accent="#f4a261"
          />
        </div>
      </section>
    </main>
  );
}

type MetricCardProps = {
  label: string;
  value: string;
  accent: string;
};

function MetricCard({ label, value, accent }: MetricCardProps) {
  return (
    <article
      style={{
        padding: "20px",
        borderRadius: "18px",
        background: "#f8fafc",
        border: `1px solid ${accent}33`,
      }}
    >
      <p
        style={{
          margin: "0 0 8px",
          fontSize: "13px",
          color: "#5c677d",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </p>
      <p
        style={{
          margin: 0,
          fontSize: "20px",
          fontWeight: 700,
          color: "#14213d",
          wordBreak: "break-word",
        }}
      >
        {value}
      </p>
    </article>
  );
}
