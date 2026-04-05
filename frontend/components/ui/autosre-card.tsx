'use client';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';

interface AutoSRECardProps {
  title?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  icon?: LucideIcon;
  variant?: 'default' | 'gradient' | 'glass' | 'elevated';
  className?: string;
  hover?: boolean;
  glow?: boolean;
}

export function AutoSRECard({
  title,
  description,
  children,
  footer,
  icon: Icon,
  variant = 'default',
  className,
  hover = true,
  glow = false
}: AutoSRECardProps) {
  const variantClasses = {
    default: 'bg-card border border-border/50',
    gradient: 'bg-gradient-to-br from-card to-primary/5 border border-primary/20',
    glass: 'bg-card/60 backdrop-blur-sm border border-border/30',
    elevated: 'bg-card border border-border/50 shadow-xl shadow-primary/5'
  };
  
  const hoverClasses = hover 
    ? 'hover:shadow-lg hover:shadow-primary/10 hover:-translate-y-1 hover:border-primary/30 transition-all duration-300' 
    : '';
    
  const glowClasses = glow ? 'animate-pulse-glow' : '';
  
  return (
    <Card className={cn(
      'relative overflow-hidden',
      variantClasses[variant],
      hoverClasses,
      glowClasses,
      className
    )}>
      {/* Background gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 hover:opacity-100 transition-opacity duration-500" />
      
      <div className="relative z-10">
        {(title || description || Icon) && (
          <CardHeader>
            <div className="flex items-center gap-3">
              {Icon && (
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
              )}
              <div className="flex-1">
                {title && (
                  <CardTitle className="text-lg font-semibold bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text">
                    {title}
                  </CardTitle>
                )}
                {description && (
                  <CardDescription className="mt-1 text-muted-foreground">
                    {description}
                  </CardDescription>
                )}
              </div>
            </div>
          </CardHeader>
        )}
        
        <CardContent className="pb-4">
          {children}
        </CardContent>
        
        {footer && (
          <CardFooter className="pt-4 border-t border-border/50">
            {footer}
          </CardFooter>
        )}
      </div>
    </Card>
  );
}