import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DISC Mali | Rapprochement des hiérarchies",
  description: "Comparer les unités d’organisation DISC-Mali et DHIS2 et valider leurs correspondances.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
