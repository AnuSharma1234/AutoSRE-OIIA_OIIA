'use client';

import { cn } from '@/lib/utils';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: 'increase' | 'decrease' | 'neutral';
    timeframe?: string;
  };
  icon?: LucideIcon;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
  format?: 'number' | 'percentage' | 'currency' | 'duration';
}

export function MetricCard({
  title,
  value,
  change,
  icon: Icon,
  variant = 'default',
  className,
  format = 'number'
}: MetricCardProps) {
  const variantClasses = {
    default: 'from-card to-primary/5 border-primary/20',
    success: 'from-card to-emerald-500/5 border-emerald-500/20',
    warning: 'from-card to-amber-500/5 border-amber-500/20',
    danger: 'from-card to-red-500/5 border-red-500/20',
    info: 'from-card to-blue-500/5 border-blue-500/20'
  };
  
  const iconColors = {
    default: 'text-primary',
    success: 'text-emerald-600',
    warning: 'text-amber-600',
    danger: 'text-red-600',
    info: 'text-blue-600'
  };
  
  const formatValue = (val: string | number) => {
    if (typeof val === 'string') return val;
    
    switch (format) {
      case 'percentage':
        return `${val}%`;
      case 'currency':
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
      case 'duration':
        return `${val}ms`;
      default:
        return val.toLocaleString();
    }
  };
  
  const getTrendIcon = () => {
    if (!change) return null;
    
    switch (change.type) {
      case 'increase':
        return <TrendingUp className="h-3 w-3" />;
      case 'decrease':
        return <TrendingDown className="h-3 w-3" />;
      default:
        return <Minus className="h-3 w-3" />;
    }
  };
  
  const getTrendColor = () => {
    if (!change) return '';
    
    switch (change.type) {
      case 'increase':
        return 'text-emerald-600 bg-emerald-50';
      case 'decrease':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };
  
  return (
    <div className={cn(
      'relative p-6 rounded-xl bg-gradient-to-br border backdrop-blur-sm',
      'hover:shadow-lg hover:shadow-primary/10 hover:-translate-y-1 transition-all duration-300',
      variantClasses[variant],
      className
    )}>
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary to-accent rounded-full transform translate-x-16 -translate-y-16" />
      </div>
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
          {Icon && (
            <div className={cn('p-1.5 rounded-lg bg-primary/10', iconColors[variant])}>
              <Icon className="h-4 w-4" />
            </div>
          )}
        </div>
        
        <div className="flex items-end justify-between">
          <div>
            <div className="text-2xl font-bold text-foreground mb-1">
              {formatValue(value)}
            </div>
            
            {change && (
              <Badge 
                variant="secondary" 
                className={cn(
                  'text-xs font-medium px-2 py-0.5 flex items-center gap-1',
                  getTrendColor()
                )}
              >
                {getTrendIcon()}
                {change.value > 0 ? '+' : ''}{change.value}%
                {change.timeframe && (
                  <span className="text-xs opacity-75">
                    {change.timeframe}
                  </span>
                )}
              </Badge>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}