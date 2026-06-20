import type { Metadata } from "next";
import "@fontsource/lxgw-wenkai";
import "./globals.css";

export const metadata: Metadata = {
  title: "有一页 OnePage",
  description: "AI 智能排版手账 MVP"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
