import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "InjectBench",
  description: "LLM prompt-injection benchmark dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
