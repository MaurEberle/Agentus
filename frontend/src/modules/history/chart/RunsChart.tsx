import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ChartBucket } from '@/modules/history/model/types';

const COLORS = {
  succeeded: 'hsl(var(--primary))',
  failed: 'hsl(var(--destructive))',
  cancelled: 'hsl(var(--muted-foreground) / 0.55)',
  timeout: 'hsl(var(--warning))',
};

export function RunsChart({ buckets }: { buckets: ChartBucket[] }) {
  const { t } = useTranslation();
  const reduced =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const max = useMemo(
    () => Math.max(1, ...buckets.map((item) => item.succeeded + item.failed + item.cancelled + item.timeout)),
    [buckets],
  );
  const width = Math.max(320, buckets.length * 22);
  const height = 160;
  const pad = { top: 8, right: 8, bottom: 28, left: 28 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const barW = buckets.length === 0 ? 0 : Math.max(4, (innerW / buckets.length) * 0.7);
  const hasTimeout = buckets.some((item) => item.timeout > 0);

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle>{t('history.chart.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        {buckets.every((item) => item.succeeded + item.failed + item.cancelled + item.timeout === 0) ? (
          <p className="text-sm text-muted-foreground">{t('history.chart.empty')}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <svg
                viewBox={`0 0 ${width} ${height}`}
                className="h-40 w-full min-w-[20rem]"
                role="img"
                aria-label={t('history.chart.title')}
              >
                {[0, 0.5, 1].map((tick) => {
                  const y = pad.top + innerH * (1 - tick);
                  const value = Math.round(max * tick);
                  return (
                    <g key={tick}>
                      <line
                        x1={pad.left}
                        x2={width - pad.right}
                        y1={y}
                        y2={y}
                        stroke="hsl(var(--border))"
                        strokeWidth={1}
                      />
                      <text x={pad.left - 6} y={y + 3} textAnchor="end" className="fill-muted-foreground" fontSize={9}>
                        {value}
                      </text>
                    </g>
                  );
                })}
                {buckets.map((bucket, index) => {
                  const x =
                    pad.left +
                    (index + 0.5) * (innerW / Math.max(1, buckets.length)) -
                    barW / 2;
                  const parts: Array<{ key: keyof typeof COLORS; value: number }> = [
                    { key: 'succeeded', value: bucket.succeeded },
                    { key: 'failed', value: bucket.failed },
                    { key: 'cancelled', value: bucket.cancelled },
                    { key: 'timeout', value: bucket.timeout },
                  ];
                  let y = pad.top + innerH;
                  const title = `${bucket.label}: ${bucket.succeeded}/${bucket.failed}/${bucket.cancelled}${hasTimeout ? `/${bucket.timeout}` : ''}`;
                  return (
                    <g key={bucket.key}>
                      <title>{title}</title>
                      {parts.map((part) => {
                        if (part.value <= 0) return null;
                        const h = (part.value / max) * innerH;
                        y -= h;
                        const rect = (
                          <rect
                            key={part.key}
                            x={x}
                            y={y}
                            width={barW}
                            height={h}
                            fill={COLORS[part.key]}
                            className={reduced ? undefined : 'transition-[y,height] duration-300'}
                          />
                        );
                        return rect;
                      })}
                      {index % Math.ceil(buckets.length / 8) === 0 ? (
                        <text
                          x={x + barW / 2}
                          y={height - 8}
                          textAnchor="middle"
                          className="fill-muted-foreground"
                          fontSize={8}
                        >
                          {bucket.label}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
              </svg>
            </div>
            <ul className="mt-2 flex flex-wrap gap-3 text-xs">
              <Legend color={COLORS.succeeded} label={t('history.outcome.succeeded')} />
              <Legend color={COLORS.failed} label={t('history.outcome.failed')} />
              <Legend color={COLORS.cancelled} label={t('history.outcome.cancelled')} />
              {hasTimeout ? <Legend color={COLORS.timeout} label={t('history.outcome.timeout')} /> : null}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <li className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </li>
  );
}
