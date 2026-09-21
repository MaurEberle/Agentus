import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const SIZE = {
  sm: 'size-3.5',
  md: 'size-4',
  lg: 'size-8',
} as const;

export function Spinner({
  className,
  size = 'md',
  label,
}: {
  className?: string;
  size?: keyof typeof SIZE;
  label?: string;
}) {
  return (
    <span
      className={cn('inline-flex items-center justify-center', className)}
      role={label ? 'status' : undefined}
      aria-label={label}
    >
      <Loader2 className={cn('animate-spin', SIZE[size])} aria-hidden />
    </span>
  );
}
