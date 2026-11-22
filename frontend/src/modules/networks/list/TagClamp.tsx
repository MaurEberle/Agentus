import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useBoxSize } from '@/hooks/useBoxSize';

const LINES = 2;
const GAP = 4; // gap-1

/** Lines that flex-wrap needs for chips of these widths in a row of `width` pixels. */
function lineCount(widths: number[], width: number): number {
  let lines = 1;
  let x = 0;
  for (const raw of widths) {
    const chip = Math.min(raw, width);
    if (x === 0) x = chip;
    else if (x + GAP + chip <= width + 0.5) x += GAP + chip;
    else {
      lines += 1;
      x = chip;
    }
  }
  return lines;
}

/** How many leading tags fit in `LINES` lines, leaving room for the "…" chip when not all fit. */
function fitCount(widths: number[], more: number, width: number): number {
  if (lineCount(widths, width) <= LINES) return widths.length;
  for (let count = widths.length - 1; count > 0; count -= 1) {
    if (lineCount([...widths.slice(0, count), more], width) <= LINES) return count;
  }
  return 0;
}

function Tag({ tag }: { tag: string }) {
  return (
    <Badge variant="outline" className="max-w-full">
      <span className="truncate">{tag}</span>
    </Badge>
  );
}

/**
 * The tags of a list row, at most two lines. What does not fit becomes "…"; hovering or
 * focusing the tags shows all of them in a small card.
 */
export function TagClamp({ tags }: { tags: string[] }) {
  const { t } = useTranslation();
  const [box, size] = useBoxSize<HTMLDivElement>();
  const measure = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(tags.length);

  useLayoutEffect(() => {
    const host = measure.current;
    if (!host || size.width <= 0) return;
    const widths = [...host.children].map((child) => child.getBoundingClientRect().width);
    const more = widths.pop() ?? 0;
    setShown(fitCount(widths, more, size.width));
  }, [tags, size.width]);

  const clipped = shown < tags.length;
  const visible = (
    <div className="flex flex-wrap gap-1">
      {tags.slice(0, shown).map((tag) => (
        <Tag key={tag} tag={tag} />
      ))}
      {clipped ? (
        <Badge variant="outline" className="text-muted-foreground" aria-hidden>
          …
        </Badge>
      ) : null}
    </div>
  );

  return (
    <div ref={box} className="relative w-full min-w-0">
      {/* Natural chip widths, measured off-screen; the last one is the "…" chip. */}
      <div ref={measure} aria-hidden className="pointer-events-none invisible absolute start-0 top-0 flex gap-1 whitespace-nowrap">
        {tags.map((tag) => (
          <Badge key={tag} variant="outline">
            {tag}
          </Badge>
        ))}
        <Badge variant="outline">…</Badge>
      </div>
      {clipped ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <div tabIndex={0} aria-label={t('networks.list.allTags', { tags: tags.join(', ') })} className="rounded-sm outline-none focus-visible:ring-1 focus-visible:ring-ring">
              {visible}
            </div>
          </TooltipTrigger>
          <TooltipContent
            side="bottom"
            align="start"
            className="max-w-72 border bg-popover p-2 text-popover-foreground"
          >
            <p className="mb-1.5 text-muted-foreground">{t('networks.list.tagCount', { count: tags.length })}</p>
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <Badge key={tag} variant="outline" className="max-w-full break-all">
                  {tag}
                </Badge>
              ))}
            </div>
          </TooltipContent>
        </Tooltip>
      ) : (
        visible
      )}
    </div>
  );
}
