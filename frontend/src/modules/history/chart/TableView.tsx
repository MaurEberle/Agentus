import { useTranslation } from 'react-i18next';
import { bucketTotal, OUTCOME_FILL, OUTCOMES } from '@/modules/history/chart/chartModel';
import type { ChartBucket } from '@/modules/history/model/types';

/** The numbers behind the timeline: one row per day (or hour) with runs, newest first. */
export function TableView({ buckets }: { buckets: ChartBucket[] }) {
  const { t, i18n } = useTranslation();
  const number = new Intl.NumberFormat(i18n.language);
  const rows = buckets.filter((bucket) => bucketTotal(bucket) > 0).reverse();
  const columns = OUTCOMES.filter((key) => key !== 'timeout' || rows.some((row) => row.timeout > 0));
  const unit = buckets[0]?.unit === 'hour' ? 'hour' : 'day';
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-1.5 pr-3 font-medium">{t(`history.chart.table.${unit}`)}</th>
            {columns.map((key) => (
              <th key={key} className="py-1.5 pr-3 text-right font-medium">
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2 rounded-sm" style={{ background: OUTCOME_FILL[key] }} aria-hidden />
                  {t(`history.outcome.${key}`)}
                </span>
              </th>
            ))}
            <th className="py-1.5 text-right font-medium">{t('history.chart.table.total')}</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row) => (
            <tr key={row.key} className="border-b last:border-b-0">
              <td className="py-1.5 pr-3">{row.label}</td>
              {columns.map((key) => (
                <td key={key} className={row[key] ? 'py-1.5 pr-3 text-right' : 'py-1.5 pr-3 text-right text-muted-foreground'}>
                  {row[key] ? number.format(row[key]) : '–'}
                </td>
              ))}
              <td className="py-1.5 text-right font-semibold">{number.format(bucketTotal(row))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
