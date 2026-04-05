import './globals.css';
import type { Metadata, Viewport } from 'next';
import { Manrope } from 'next/font/google';
import { Providers } from '@/lib/providers';
import { DevModeIndicator } from '@/components/dev-mode-indicator';

export const metadata: Metadata = {
  title: 'AutoSRE',
  description: 'Autonomous Site Reliability Engineering platform. AI-powered infrastructure management with intelligent incident response and automated remediation capabilities.'
};

export const viewport: Viewport = {
  maximumScale: 1
};

const manrope = Manrope({ subsets: ['latin'] });

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`bg-page text-text-main ${manrope.className}`}
    >
      <body className="min-h-[100dvh] bg-page font-sans" suppressHydrationWarning>
        <Providers>
          {children}
          <DevModeIndicator />
        </Providers>
      </body>
    </html>
  );
}
