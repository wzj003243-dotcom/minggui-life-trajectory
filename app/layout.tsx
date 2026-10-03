import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "命轨 MingGui — Life Trajectory Lab",
  description: "传统命理先验 × 生平数据 × 可验证人生轨迹预测",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="nav shell">
          <a className="brand" href="/">
            <span className="seal">命</span>
            <span>命轨 <small>MingGui</small></span>
          </a>
          <nav>
            <a href="/analyze">推演</a>
            <a href="/research">实验室</a>
          </nav>
        </header>
        {children}
        <footer className="shell footer">
          <span>命理是先验，不是判决。</span>
          <span>Research preview · probabilistic & falsifiable</span>
        </footer>
      </body>
    </html>
  );
}
