import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ENIAK · Evidence-Native Intelligent Academic Kernel",
  description:
    "An open research operating layer for traceable, book-quality knowledge work.",
  metadataBase: new URL("https://www.eniak.org"),
  openGraph: {
    title: "ENIAK",
    description: "Evidence-native research workflows.",
    url: "https://www.eniak.org",
    siteName: "ENIAK",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-ink-200/70 bg-paper/80 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-baseline gap-3 group">
            <span className="font-display text-2xl font-semibold tracking-tight text-ink-900">
              ENIAK
            </span>
            <span className="text-xs text-ink-400 hidden sm:inline">
              Evidence-Native Intelligent Academic Kernel
            </span>
          </a>
          <nav className="flex items-center gap-5 text-sm text-ink-600">
            <a className="hover:text-ink-900" href="/">
              Runs
            </a>
            <a className="hover:text-ink-900" href="/books">
              Books
            </a>
            <a
              className="hover:text-ink-900"
              href="https://github.com/yupoet/eniak"
              target="_blank"
              rel="noreferrer"
            >
              GitHub ↗
            </a>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
      <footer className="mx-auto max-w-5xl px-6 pb-10 pt-6 text-xs text-ink-400">
        <p>Apache-2.0 · Evidence-native, human-gated, book-shaped.</p>
      </footer>
    </div>
  );
}
