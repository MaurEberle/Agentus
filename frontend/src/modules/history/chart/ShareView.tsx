import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useBoxSize } from '@/hooks/useBoxSize';
import { ChartTooltip, type TooltipState } from '@/modules/history/chart/ChartTooltip';
import { OUTCOME_FILL, OUTCOME_INK, OUTCOMES, outcomeTotals } from '@/modules/history/chart/chartModel';
import type { ChartBucket } from '@/modules/history/model/types';

const LABEL_ROOM = 44; // a block narrower than this prints no share; hover and the table have it

/**
 * How the runs of the range ended, as one whole: a tall segmented bar (the readable form
 * of a pie for a few parts), its legend, and the numbers as a table below.
 */
export function ShareView({ buckets }: { buckets: ChartBucket[] }) {
  const { t, i18n } = useTranslation();
  const [box, size] = useBoxSize<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const totals = outcomeTotals(buckets);
  const number = new Intl.NumberFormat(i18n.language);
  const parts = OUTCOMES.filter((key) => totals[key] > 0);
  const share = (value: number) => Math.round((value / Math.max(1, totals.total)) * 100);
  // Blocks share the width less the 2px gaps between them.
  const usable = Math.max(0, size.width - 2 * Math.max(0, parts.length - 1));

  let offset = 0;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-auto">
      <div ref={box} className="relative pt-1">
        <div
          className="flex h-7 w-full gap-0.5"
          role="img"
          aria-label={parts.map((key) => `${t(`history.outcome.${key}`)} ${totals[key]} (${share(totals[key])} %)`).join(', ')}
        >
          {parts.map((key) => {
            const width = (totals[key] / totals.total) * usable;
            const left = offset;
            offset += width + 2;
            const state: TooltipState = {
              x: left + width / 2,
              y: 0,
              title: t(`history.outcome.${key}`),
              rows: [{ key, value: totals[key], share: share(totals[key]) }],
            };
            return (
              <div
                key={key}
                tabIndex={0}
                className="flex h-full min-w-0 items-center rounded px-2 text-xs font-semibold outline-none ring-offset-1 focus-visible:ring-2 focus-visible:ring-ring"
                style={{ flexGrow: totals[key], flexBasis: 0, background: OUTCOME_FILL[key], color: OUTCOME_INK[key] }}
                onPointerEnter={() => setTip(state)}
                onPointerLeave={() => setTip(null)}
                onFocus={() => setTip(state)}
                onBlur={() => setTip(null)}
              >
                {width >= LABEL_ROOM ? `${share(totals[key])} %` : null}
              </div>
            );
          })}
        </div>
        <ChartTooltip state={tip} width={size.width} />
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {parts.map((key) => (
          <li key={key} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: OUTCOME_FILL[key] }} aria-hidden />
            {t(`history.outcome.${key}`)}
          </li>
        ))}
      </ul>
      <table className="w-full max-w-md text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-1 pr-3 font-medium">{t('history.chart.table.outcome')}</th>
            <th className="py-1 pr-3 text-right font-medium">{t('history.chart.table.runs')}</th>
            <th className="py-1 text-right font-medium">{t('history.chart.table.share')}</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {OUTCOMES.filter((key) => totals[key] > 0 || key !== 'timeout').map((key) => (
            <tr key={key} className="border-b last:border-b-0">
              <td className="py-1 pr-3">
                <span className="flex items-center gap-2">
                  <span className="size-2.5 rounded-sm" style={{ background: OUTCOME_FILL[key] }} aria-hidden />
                  {t(`history.outcome.${key}`)}
                </span>
              </td>
              <td className="py-1 pr-3 text-right">{number.format(totals[key])}</td>
              <td className="py-1 text-right">{share(totals[key])} %</td>
            </tr>
          ))}
          <tr className="font-semibold">
            <td className="py-1 pr-3">{t('history.chart.table.total')}</td>
            <td className="py-1 pr-3 text-right">{number.format(totals.total)}</td>
            <td className="py-1 text-right">100 %</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
