import type { Metadata } from "next";
import { Spectral, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const spectral = Spectral({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Trợ lý Pháp lý — Lao động & Thuế",
  description: "Hỏi đáp có trích dẫn Điều khoản, dựa trên Bộ luật Lao động và các Luật Thuế hiện hành.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={`${spectral.variable} ${plexSans.variable}`}>{children}</body>
    </html>
  );
}
