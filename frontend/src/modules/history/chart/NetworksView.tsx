import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useBoxSize } from '@/hooks/useBoxSize';
import { ChartTooltip, type TooltipState } from '@/modules/history/chart/ChartTooltip';
import { networkRows, OUTCOME_FILL, OUTCOMES } from '@/modules/history/chart/chartModel';
import type { RunSummary } from '@/modules/history/model/types';

/** Runs per network, most first, each bar split by outcome on one shared scale. */
export function NetworksView({ runs }: { runs: RunSummary[] }) {
  const { t, i18n } = useTranslation();
  const [box, size] = useBoxSize<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const rows = useMemo(() => networkRows(runs), [runs]);
  const max = Math.max(1, ...rows.map((row) => row.total));
  const number = new Intl.NumberFormat(i18n.language);

  return (
    <div ref={box} className="relative min-h-0 flex-1 overflow-auto">
      <ul className="space-y-2">
        {rows.map((row) => {
          const name = row.more ? t('history.chart.moreNetworks', { count: row.more }) : row.name;
          const segments = OUTCOMES.filter((key) => row[key] > 0);
          const show = (event: { currentTarget: HTMLElement }) => {
            const rect = event.currentTarget.getBoundingClientRect();
            const host = box.current?.getBoundingClientRect();
            setTip({
              x: host ? rect.left - host.left + rect.width * (row.total / max) : 0,
              y: host ? rect.top - host.top + (box.current?.scrollTop ?? 0) : 0,
              title: name,
              lead: t('history.chart.runs', { count: row.total, formatted: number.format(row.total) }),
              rows: segments.map((key) => ({ key, value: row[key] })),
            });
          };
          return (
            <li
              key={row.key}
              tabIndex={0}
              className="grid grid-cols-[minmax(6rem,30%)_minmax(0,1fr)] items-center gap-3 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`${name}: ${segments.map((key) => `${row[key]} ${t(`history.outcome.${key}`)}`).join(', ')}`}
              onPointerEnter={show}
              onPointerLeave={() => setTip(null)}
              onFocus={show}
              onBlur={() => setTip(null)}
            >
              <span className={row.more ? 'truncate text-sm text-muted-foreground' : 'truncate text-sm'} title={name}>
                {name}
              </span>
              <span className="flex min-w-0 items-center gap-2">
                <span className="flex h-3.5 min-w-0 gap-0.5" style={{ width: `${(row.total / max) * 85}%` }}>
                  {segments.map((key, index) => (
                    <span
                      key={key}
                      className={index === segments.length - 1 ? 'h-full rounded-r' : 'h-full'}
                      style={{ flexGrow: row[key], flexBasis: 0, background: OUTCOME_FILL[key] }}
                    />
                  ))}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{number.format(row.total)}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <ChartTooltip state={tip} width={size.width} />
    </div>
  );
}
