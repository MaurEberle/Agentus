import { useLayoutEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { formatDateTime } from '@/modules/history/model/format';
import { NO_ERROR_KEY } from '@/modules/history/model/stats';
import { squarify } from '@/modules/history/model/treemap';
import type { ErrorClass, ErrorTile } from '@/modules/history/model/types';
import { limitLabel } from '@/modules/monitoring/model/logView';
import { moduleCardClass } from '@/modules/moduleCard';

// One hue per error class; the area tells how often, the colour what kind.
const CLASS_TONE: Record<ErrorClass, string> = {
  orchestrator: 'border-amber-500/50 bg-amber-500/15 hover:bg-amber-500/25',
  llm_error: 'border-rose-500/50 bg-rose-500/15 hover:bg-rose-500/25',
  tool_error: 'border-violet-500/50 bg-violet-500/15 hover:bg-violet-500/25',
  timeout: 'border-sky-500/50 bg-sky-500/15 hover:bg-sky-500/25',
  budget: 'border-orange-500/50 bg-orange-500/15 hover:bg-orange-500/25',
  validation: 'border-teal-500/50 bg-teal-500/15 hover:bg-teal-500/25',
  service: 'border-slate-500/50 bg-slate-500/15 hover:bg-slate-500/25',
  unknown: 'border-zinc-500/40 bg-zinc-500/10 hover:bg-zinc-500/20',
};
const GAP = 4;

type TileSize = 'tiny' | 'small' | 'normal' | 'roomy';

// How much a tile shows: tiny ones the count and one line, roomy ones also nodes and date.
function tileSize(width: number, height: number): TileSize {
  if (width < 64 || height < 44) return 'tiny';
  if (width < 110 || height < 72) return 'small';
  if (width >= 150 && height >= 120) return 'roomy';
  return 'normal';
}

// Label classes, its line height, and the height the rest of the tile takes (padding,
// count row, details) for each size.
const SIZE_STYLE: Record<TileSize, { label: string; lineHeight: number; reserved: number; count: string }> = {
  tiny: { label: 'text-[11px]', lineHeight: 13, reserved: 34, count: 'text-sm' },
  small: { label: 'text-xs', lineHeight: 15, reserved: 40, count: 'text-base' },
  normal: { label: 'text-xs', lineHeight: 16, reserved: 46, count: 'text-xl' },
  roomy: { label: 'text-sm', lineHeight: 19, reserved: 84, count: 'text-3xl' },
};

function useBoxSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const update = () => setSize({ width: element.clientWidth, height: element.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

/**
 * Error map: every error key of the failed runs is a tile, its area the number of runs.
 * A click filters the history by it; a second click, or the chip in the head, lifts it.
 */
export function ErrorMap({
  tiles,
  activeError,
  onPick,
  onClear,
}: {
  tiles: ErrorTile[];
  /** Error filter of the history ('' for none). */
  activeError: string;
  onPick: (tile: ErrorTile) => void;
  onClear: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [box, size] = useBoxSize<HTMLDivElement>();
  const total = tiles.reduce((sum, tile) => sum + tile.count, 0);
  const rects = squarify(
    tiles.map((tile) => tile.count),
    { x: 0, y: 0, w: size.width, h: size.height },
  );
  const labelOf = (tile: ErrorTile) => {
    if (tile.more) return t('history.errors.more', { count: tile.more });
    if (tile.error === NO_ERROR_KEY) return t('history.errors.noKey');
    // The run keeps only the key; texts with values ({{decisions}}) show without them.
    return limitLabel(tile.error ?? '', t) || (tile.error ?? '');
  };
  const active = tiles.find((tile) => tile.error === activeError);

  return (
    <Card className={cn(moduleCardClass, 'h-full min-w-0')}>
      <CardHeader className="shrink-0 pb-2">
        {/* Fixed height: the filter chip must not change the map's size and reshuffle the tiles. */}
        <div className="flex h-7 min-w-0 items-center justify-between gap-2">
          <CardTitle>{t('history.errors.title')}</CardTitle>
          {activeError ? (
            <Button type="button" size="sm" variant="secondary" className="h-7 min-w-0 max-w-[70%] gap-1 px-2" onClick={onClear}>
              <span className="truncate">
                {t('history.errors.filtered', { name: active ? labelOf(active) : activeError })}
              </span>
              <X className="size-3.5 shrink-0" aria-hidden />
            </Button>
          ) : total > 0 ? (
            <span className="truncate text-xs text-muted-foreground">{t('history.errors.total', { count: total })}</span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        {tiles.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('history.errors.empty')}</p>
        ) : (
          <div ref={box} className="relative min-h-[8rem] flex-1" role="list" aria-label={t('history.errors.title')}>
            {tiles.map((tile, index) => {
              const rect = rects[index];
              if (!rect || rect.w <= 0 || rect.h <= 0) return null;
              const width = rect.w - GAP;
              const height = rect.h - GAP;
              const size = tileSize(width, height);
              const share = Math.round((tile.count / total) * 100);
              const label = labelOf(tile);
              const selected = Boolean(activeError) && tile.error === activeError;
              const dimmed = Boolean(activeError) && !selected;
              const clickable = !tile.more;
              const nodes = tile.nodes.map((node) => node.name).join(', ');
              const className = t(`history.errorClass.${tile.errorClass}`, { defaultValue: tile.errorClass });
              const last = t('history.errors.last', { date: formatDateTime(tile.lastAt, i18n.language) });
              const title = [
                label,
                `${t('history.errors.runs', { count: tile.count })} · ${share} %`,
                className + (nodes ? ` · ${nodes}` : ''),
                last,
              ].join('\n');
              // The label takes the lines left over by padding, the count row and the details.
              const style = SIZE_STYLE[size];
              const lines = Math.max(1, Math.min(8, Math.floor((height - style.reserved) / style.lineHeight)));
              return (
                <button
                  key={tile.id}
                  type="button"
                  role="listitem"
                  title={title}
                  disabled={!clickable}
                  aria-pressed={clickable ? selected : undefined}
                  onClick={() => clickable && onPick(tile)}
                  className={cn(
                    'absolute flex flex-col overflow-hidden rounded-md border text-left text-foreground transition',
                    size === 'tiny' ? 'p-1.5' : 'p-2',
                    CLASS_TONE[tile.errorClass] ?? CLASS_TONE.unknown,
                    clickable ? 'cursor-pointer' : 'cursor-default',
                    selected && 'ring-2 ring-primary ring-offset-1 ring-offset-background',
                    dimmed && 'opacity-40 hover:opacity-80',
                  )}
                  style={{ left: rect.x, top: rect.y, width, height }}
                >
                  {size === 'tiny' ? null : (
                  <span
                    className={cn('min-w-0 hyphens-auto break-words font-medium', style.label)}
                    style={{
                      display: '-webkit-box',
                      WebkitLineClamp: lines,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      lineHeight: `${style.lineHeight}px`,
                    }}
                  >
                    {label}
                  </span>
                  )}
                  <span className="mt-auto flex min-w-0 items-end justify-between gap-2 pt-1">
                    <span className={cn('shrink-0 font-mono font-semibold tabular-nums leading-none', style.count)}>
                      {tile.count}
                    </span>
                    {size === 'normal' || size === 'roomy' ? (
                      <span className="min-w-0 truncate text-right text-[11px] leading-tight text-muted-foreground">
                        {share} % · {className}
                      </span>
                    ) : null}
                  </span>
                  {size === 'roomy' ? (
                    <span className="min-w-0 pt-0.5 text-[11px] leading-tight text-muted-foreground">
                      {nodes ? <span className="block truncate">{nodes}</span> : null}
                      <span className="block truncate">{last}</span>
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
