import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TUBITAK Proposal Evaluator",
  description: "Health status dashboard for the evaluation platform.",
};

type RootLayoutProps = Readonly<{
  children: React.ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
