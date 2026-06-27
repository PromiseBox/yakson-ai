import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "약손 AI — 복약 안전을 위한 AI 에이전트",
  description: "노인 복약 안전 점검 리포트",
  icons: {
    icon: "/favicon.svg"
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f9f6e"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
