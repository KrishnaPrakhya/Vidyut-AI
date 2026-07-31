import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vidyut Backend Explorer",
  description: "A basic interactive demonstrator for the Vidyut backend.",
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
