import type { Metadata } from "next";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "TUBITAK Proposal Evaluator",
  description: "Health status dashboard for the evaluation platform.",
};

type RootLayoutProps = Readonly<{
  children: React.ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="tr" className={styles.html}>
      <body className={styles.body}>{children}</body>
    </html>
  );
}
