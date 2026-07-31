import type { Metadata } from "next";
import "./globals.css";
import "./experience.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: "Vidyut | Grid Intelligence Replay",
  description: "Replay, simulate and verify targeted electrical distribution network responses.",
  applicationName: "Vidyut",
  keywords: ["electrical distribution", "load balancing", "grid simulation", "demand response"],
  openGraph: {
    title: "Vidyut | Prevent blackouts before they happen",
    description: "A recorded, auditable digital twin for targeted electrical distribution response.",
    type: "website",
    images: [{ url: "/vidyut-grid-preview.png", width: 1672, height: 941, alt: "Vidyut distribution grid protecting homes and a hospital" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vidyut | Prevent blackouts before they happen",
    description: "A recorded, auditable digital twin for targeted electrical distribution response.",
    images: ["/vidyut-grid-preview.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
