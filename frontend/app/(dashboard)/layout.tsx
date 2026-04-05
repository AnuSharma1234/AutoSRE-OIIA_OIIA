import { Suspense } from 'react';
import { Navigation } from '@/components/navigation';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <section className="flex flex-col min-h-screen">
      <Suspense fallback={<div className="h-16 border-b border-border-line" />}>
        <Navigation />
      </Suspense>
      <main className="flex-1 bg-page">
        {children}
      </main>
    </section>
  );
}
