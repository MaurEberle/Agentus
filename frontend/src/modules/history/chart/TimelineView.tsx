import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useBoxSize } from '@/hooks/useBoxSize';
import { ChartTooltip, type TooltipState } from '@/modules/history/chart/ChartTooltip';
import {
  bucketTotal,
  compressTimeline,
  niceTicks,
  OUTCOME_FILL,
  OUTCOMES,
  type TimelineItem,
} from '@/modules/history/chart/chartModel';
import type { ChartBucket } from '@/modules/history/model/types';

const PAD = { top: 10, right: 8, bottom: 24, left: 34 };
const GAP_WIDTH = 18; // a stretch of days without runs, however long
const BAND_MIN = 14;
const BAND_MAX = 64;
const BAR_MAX = 24; // marks stay thin: the band's leftover is air
const SEGMENT_GAP = 2; // surface gap between stacked segments
const RADIUS = 4;
const LABEL_WIDTH = 48;

function topPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, height, width / 2);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}

/**
 * Runs per day (or hour), stacked by outcome. Days without runs collapse into one narrow
 * gap per stretch, so a 30-day range is as wide as the days that had runs.
 */
export function TimelineView({ buckets }: { buckets: ChartBucket[] }) {
  const { t, i18n } = useTranslation();
  const [box, size] = useBoxSize<HTMLDivElement>();
  const [hover, setHover] = useState<{ key: string; tip: TooltipState } | null>(null);
  const items = useMemo(() => compressTimeline(buckets), [buckets]);
  const bars = items.filter((item) => item.kind === 'bar').length;
  const gaps = items.length - bars;
  const max = Math.max(1, ...items.map((item) => (item.kind === 'bar' ? bucketTotal(item.bucket) : 0)));
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1];
  const number = new Intl.NumberFormat(i18n.language);

  const plotW = Math.max(0, size.width - PAD.left - PAD.right);
  const plotH = Math.max(0, size.height - PAD.top - PAD.bottom);
  const band = bars === 0 ? 0 : Math.min(BAND_MAX, Math.max(BAND_MIN, (plotW - gaps * GAP_WIDTH) / bars));
  const contentW = bars * band + gaps * GAP_WIDTH;
  const svgWidth = Math.max(size.width, contentW + PAD.left + PAD.right);
  const start = PAD.left + Math.max(0, (plotW - contentW) / 2);
  const barW = Math.min(BAR_MAX, band * 0.62);
  const labelEvery = Math.max(1, Math.ceil(LABEL_WIDTH / Math.max(1, band)));
  const baseline = PAD.top + plotH;
  const scale = plotH / top;

  const placed: { item: TimelineItem; x: number; width: number; index: number }[] = [];
  let cursor = start;
  let barIndex = 0;
  for (const item of items) {
    const width = item.kind === 'bar' ? band : GAP_WIDTH;
    placed.push({ item, x: cursor, width, index: item.kind === 'bar' ? barIndex++ : -1 });
    cursor += width;
  }

  function tipFor(item: TimelineItem, x: number): TooltipState {
    if (item.kind === 'gap') {
      const unit = item.first.unit === 'hour' ? 'hours' : 'days';
      const range = item.count > 1 ? `${item.first.label} – ${item.last.label}` : item.first.label;
      return { x, y: baseline - 40, title: range, lead: t(`history.chart.gap.${unit}`, { count: item.count }), rows: [] };
    }
    const total = bucketTotal(item.bucket);
    const height = total * scale;
    return {
      x,
      y: baseline - height,
      title: item.bucket.label,
      lead: t('history.chart.runs', { count: total, formatted: number.format(total) }),
      rows: OUTCOMES.filter((key) => item.bucket[key] > 0).map((key) => ({ key, value: item.bucket[key] })),
    };
  }

  return (
    <div ref={box} className="relative min-h-[10rem] flex-1 overflow-x-auto overflow-y-hidden">
      {size.width > 0 && size.height > 0 ? (
        <svg width={svgWidth} height={size.height} className="block" role="img" aria-label={t('history.chart.views.timeline')}>
          {ticks.map((tick) => {
            const y = baseline - tick * scale;
            return (
              <g key={tick}>
                <line x1={PAD.left} x2={svgWidth - PAD.right} y1={y} y2={y} stroke="hsl(var(--border))" strokeWidth={1} />
                <text
                  x={PAD.left - 6}
                  y={y + 3.5}
                  textAnchor="end"
                  fontSize={11}
                  className="fill-muted-foreground"
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {number.format(tick)}
                </text>
              </g>
            );
          })}
          {placed.map(({ item, x, width, index }) => {
            const center = x + width / 2;
            const hovered = hover?.key === item.key;
            if (item.kind === 'gap') {
              return (
                <g key={item.key}>
                  <rect
                    x={x}
                    y={PAD.top}
                    width={width}
                    height={plotH}
                    fill={hovered ? 'hsl(var(--muted) / 0.6)' : 'transparent'}
                    tabIndex={0}
                    aria-label={tipFor(item, center).lead}
                    onPointerEnter={() => setHover({ key: item.key, tip: tipFor(item, center) })}
                    onPointerLeave={() => setHover(null)}
                    onFocus={() => setHover({ key: item.key, tip: tipFor(item, center) })}
                    onBlur={() => setHover(null)}
                  />
                  <text x={center} y={baseline - 4} textAnchor="middle" fontSize={12} className="pointer-events-none fill-muted-foreground">
                    ⋯
                  </text>
                </g>
              );
            }
            const barX = center - barW / 2;
            const segments = OUTCOMES.filter((key) => item.bucket[key] > 0);
            let y = baseline;
            const tip = tipFor(item, center);
            return (
              <g key={item.key}>
                <rect
                  x={x}
                  y={PAD.top}
                  width={width}
                  height={plotH + PAD.bottom}
                  fill={hovered ? 'hsl(var(--muted) / 0.6)' : 'transparent'}
                  tabIndex={0}
                  aria-label={`${item.bucket.label}: ${tip.lead}, ${tip.rows
                    .map((row) => `${row.value} ${t(`history.outcome.${row.key}`)}`)
                    .join(', ')}`}
                  onPointerEnter={() => setHover({ key: item.key, tip })}
                  onPointerLeave={() => setHover(null)}
                  onFocus={() => setHover({ key: item.key, tip })}
                  onBlur={() => setHover(null)}
                />
                {segments.map((key, position) => {
                  const full = item.bucket[key] * scale;
                  // Every segment above the first leaves a surface gap below itself.
                  const gap = position > 0 ? Math.min(SEGMENT_GAP, full / 2) : 0;
                  const height = full - gap;
                  y -= full;
                  const last = position === segments.length - 1;
                  return last ? (
                    <path key={key} d={topPath(barX, y, barW, height)} fill={OUTCOME_FILL[key]} className="pointer-events-none" />
                  ) : (
                    <rect key={key} x={barX} y={y} width={barW} height={height} fill={OUTCOME_FILL[key]} className="pointer-events-none" />
                  );
                })}
                {index % labelEvery === 0 ? (
                  <text
                    x={center}
                    y={baseline + 16}
                    textAnchor="middle"
                    fontSize={11}
                    className="pointer-events-none fill-muted-foreground"
                  >
                    {item.bucket.axisLabel}
                  </text>
                ) : null}
              </g>
            );
          })}
          <line x1={PAD.left} x2={svgWidth - PAD.right} y1={baseline} y2={baseline} stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth={1} />
        </svg>
      ) : null}
      <ChartTooltip state={hover?.tip ?? null} width={size.width} />
    </div>
  );
}
