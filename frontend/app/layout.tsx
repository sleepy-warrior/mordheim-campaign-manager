import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mordheim Campaign Manager",
  description: "Campaign management foundation for Mordheim.",
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
