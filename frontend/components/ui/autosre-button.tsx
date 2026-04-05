'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';

interface AutoSREButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'gradient';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  icon?: LucideIcon;
  iconPosition?: 'left' | 'right';
  glow?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

export function AutoSREButton({
  children,
  variant = 'primary',
  size = 'md',
  className,
  icon: Icon,
  iconPosition = 'left',
  glow = false,
  onClick,
  disabled = false,
  type = 'button'
}: AutoSREButtonProps) {
  const baseClasses = 'relative overflow-hidden transition-all duration-300 font-medium';
  
  const variantClasses = {
    primary: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg hover:shadow-xl',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
    outline: 'border-2 border-primary/30 text-primary hover:bg-primary/10 hover:border-primary/50',
    ghost: 'text-primary hover:bg-primary/10',
    gradient: 'bg-gradient-to-r from-primary to-accent text-white hover:from-primary/90 hover:to-accent/90 shadow-lg hover:shadow-xl'
  };
  
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm rounded-lg',
    md: 'px-4 py-2 text-sm rounded-lg',
    lg: 'px-6 py-3 text-base rounded-xl'
  };
  
  const glowClasses = glow ? 'animate-pulse-glow' : '';
  
  return (
    <Button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        baseClasses,
        variantClasses[variant],
        sizeClasses[size],
        glowClasses,
        className
      )}
    >
      <div className="flex items-center gap-2 relative z-10">
        {Icon && iconPosition === 'left' && <Icon className="h-4 w-4" />}
        {children}
        {Icon && iconPosition === 'right' && <Icon className="h-4 w-4" />}
      </div>
      
      {/* Gradient overlay for hover effect */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] hover:translate-x-[100%] transition-transform duration-700 ease-in-out" />
    </Button>
  );
}