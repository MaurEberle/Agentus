import appIcon from '@/assets/brand/app-icon.png';
import spinningIcon from '@/assets/brand/spinning-agentus.gif';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';

export function BrandMark({
  className,
  alt = '',
  spinning = false,
}: {
  className?: string;
  alt?: string;
  spinning?: boolean;
}) {
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  return (
    <img
      src={spinning && !reducedMotion ? spinningIcon : appIcon}
      alt={alt}
      className={cn('shrink-0 object-contain', className)}
      draggable={false}
    />
  );
}
