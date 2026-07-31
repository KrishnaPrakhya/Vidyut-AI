import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vidyut — Distribution Network Load Balancing",
  description:
    "Dynamic load balancing for electrical distribution networks using demand flexibility, forecasting, and feeder reconfiguration.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header>
            <div className="brand">
              <b>⚡</b>
              <span>
                <small>DEMO SIMULATION PLATFORM</small>
                <strong>VIDYUT</strong>
              </span>
            </div>
            <nav aria-label="Main Navigation">
              <Link href="/">Console</Link>
              <b>/</b>
              <Link href="/models">ML Models</Link>
              <b>/</b>
              <Link href="/about">About & Scope</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer>
            <span>Vidyut Distribution Automation & Load Balancing</span>
            <span>Simulated Network • Not Connected to Live Utility</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
