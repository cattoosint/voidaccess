import type { Metadata } from "next";
import { Outfit, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { KeyboardShortcutsProvider } from "@/components/KeyboardShortcutsProvider";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-outfit",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "VoidAccess — Dark Web Intelligence",
  description: "Professional dark web OSINT platform for threat intelligence teams.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${outfit.variable} ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased text-[var(--text-primary)] bg-[var(--bg-void)]">
        <KeyboardShortcutsProvider>
          {children}
        </KeyboardShortcutsProvider>
      </body>
    </html>
  );
}
