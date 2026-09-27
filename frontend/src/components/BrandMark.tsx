import appIcon from '@/assets/brand/app-icon.png';
import chillyIcon from '@/assets/brand/chilly_agentus_v2.gif';
import spinningIcon from '@/assets/brand/spinning-agentus.gif';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';

/** GIF canvas has more empty margin than the PNG; scale so the mascot matches. */
const SPIN_MATCH_PNG = 'origin-[41.17%_51.08%] translate-x-[8.83%] -translate-y-[1.08%] scale-[1.266]';

export function BrandMark({
  className,
  alt = '',
  spinning = false,
  chill = false,
}: {
  className?: string;
  alt?: string;
  spinning?: boolean;
  chill?: boolean;
}) {
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const spin = spinning && !reducedMotion;
  const idle = !spin && chill && !reducedMotion;
  return (
    <span className={cn('relative inline-flex shrink-0 overflow-visible', className)}>
      <img
        src={spin ? spinningIcon : idle ? chillyIcon : appIcon}
        alt={alt}
        draggable={false}
        className={cn('pointer-events-none size-full max-w-none object-contain', spin && SPIN_MATCH_PNG)}
      />
    </span>
  );
}
