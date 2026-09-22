import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "农业智能分析系统",
  description: "基于航拍影像的作物分类、长势分析与三维农田可视化平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
