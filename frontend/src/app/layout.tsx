import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Paste-to-Product — AI style advice → real buyable products',
  description:
    'Paste any AI style advice chat. We extract every shoppable item, find real products with confidence scores, and compare prices across platforms.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
