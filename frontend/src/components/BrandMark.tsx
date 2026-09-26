import appIcon from '@/assets/brand/app-icon.png';
import spinningIcon from '@/assets/brand/spinning-agentus.gif';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';

/** GIF canvas has more empty margin than the PNG; scale so the mascot matches. */
const SPIN_MATCH_PNG = 'origin-[41.17%_51.08%] translate-x-[8.83%] -translate-y-[1.08%] scale-[1.266]';

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
  const animate = spinning && !reducedMotion;
  return (
    <span className={cn('relative inline-flex shrink-0 overflow-visible', className)}>
      <img
        src={animate ? spinningIcon : appIcon}
        alt={alt}
        draggable={false}
        className={cn('pointer-events-none size-full max-w-none object-contain', animate && SPIN_MATCH_PNG)}
      />
    </span>
  );
}
