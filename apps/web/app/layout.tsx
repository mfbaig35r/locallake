import type { ReactNode } from "react";
import { QueryProvider } from "@/components/providers/query-provider";
import "./globals.css";

export const metadata = {
  title: "LocalLake",
  description: "Local-first Databricks-style workbench",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
