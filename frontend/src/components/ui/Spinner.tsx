import { cn } from '@/lib/util';

export interface SpinnerProps {
  className?: string;
}

export function Spinner({ className }: SpinnerProps) {
  return (
    <div
      className={cn(
        'h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600',
        className
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
