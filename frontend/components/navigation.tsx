'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';

const navItems = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/ai-control', label: 'AI Agents' },
  { href: '/incidents', label: 'Incidents' },
  { href: '/integrations', label: 'Integrations' },
  { href: '/settings', label: 'Settings' }
];

export function Navigation() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    router.push('/');
  };

  return (
    <nav className="bg-card border-b border-border-line">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14">
          
          {/* Left side - Logo and nav items */}
          <div className="flex items-center">
            {/* Logo */}
            <Link href="/" className="flex items-center text-text-main hover:text-info transition-none mr-8">
              <span className="text-xl font-bold font-mono tracking-tight">
                AutoSRE_
              </span>
            </Link>

            {/* Desktop navigation */}
            <div className="hidden md:flex space-x-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      px-3 py-2 rounded-md text-sm font-medium transition-none
                      ${isActive
                        ? 'bg-[#21262d] text-text-main'
                        : 'text-text-muted hover:bg-[#21262d] hover:text-text-main'
                      }
                    `}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Right side - User menu items */}
          <div className="flex items-center space-x-2">
            <Link
              href="/dashboard/general"
              className="px-3 py-1.5 rounded-md text-sm font-medium text-text-muted hover:bg-[#21262d] hover:text-text-main transition-none"
            >
              Account
            </Link>
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded-md text-sm font-medium text-text-muted hover:bg-[#21262d] hover:text-critical transition-none"
            >
              Logout
            </button>
          </div>
          
        </div>
      </div>
    </nav>
  );
}