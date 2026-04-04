import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';
import Providers from '@/components/Providers';

export const metadata: Metadata = {
  title: 'AutoSRE',
  description: 'Incident management and cluster monitoring',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#fafafa]">
        <Providers>
          <nav className="bg-white border-b border-zinc-200 px-6 py-4">
            <div className="flex items-center gap-10">
              <Link href="/" className="text-lg font-bold tracking-tight text-zinc-900 uppercase">
                AutoSRE
              </Link>
              <div className="flex gap-6">
                <Link
                  href="/incidents"
                  className="text-sm font-medium text-zinc-500 hover:text-indigo-600 transition-colors"
                >
                  Incidents
                </Link>
                <Link
                  href="/cluster"
                  className="text-sm font-medium text-zinc-500 hover:text-indigo-600 transition-colors"
                >
                  Cluster
                </Link>
              </div>
            </div>
          </nav>
          <main className="p-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
