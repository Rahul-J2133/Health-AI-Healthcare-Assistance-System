import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthAI — Patient Care Assistant",
  description: "AI-driven IoT-enabled personalized healthcare assistance system",
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
