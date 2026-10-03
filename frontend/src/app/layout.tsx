import type { Metadata, Viewport } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import "./globals.css";

// Be Vietnam Pro is drawn for Vietnamese: stacked diacritics (ệ, ở, ữ)
// stay legible at body sizes, which is the whole reading load here.
const beVietnam = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Trợ lý Pháp lý | Lao động và Thuế",
  description: "Hỏi đáp có trích dẫn Điều, Khoản, dựa trên Bộ luật Lao động và các Luật Thuế đang có hiệu lực.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f6f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1214" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={beVietnam.variable}>{children}</body>
    </html>
  );
}
