import { useState } from 'react';
import { BarChart3, ChartNoAxesGantt, Rows3, Table2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { bucketTotal, OUTCOME_FILL, OUTCOMES } from '@/modules/history/chart/chartModel';
import { NetworksView } from '@/modules/history/chart/NetworksView';
import { ShareView } from '@/modules/history/chart/ShareView';
import { TableView } from '@/modules/history/chart/TableView';
import { TimelineView } from '@/modules/history/chart/TimelineView';
import type { ChartBucket, RunSummary } from '@/modules/history/model/types';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';

type ChartView = 'timeline' | 'share' | 'networks' | 'table';

const VIEWS: { id: ChartView; icon: typeof BarChart3 }[] = [
  { id: 'timeline', icon: BarChart3 },
  { id: 'share', icon: ChartNoAxesGantt },
  { id: 'networks', icon: Rows3 },
  { id: 'table', icon: Table2 },
];
const VIEW_KEY = 'agentus.history.chartView';

function loadView(): ChartView {
  try {
    const raw = window.localStorage.getItem(VIEW_KEY);
    if (VIEWS.some((view) => view.id === raw)) return raw as ChartView;
  } catch {
    // Storage can be blocked; the timeline is the default.
  }
  return 'timeline';
}

function saveView(view: ChartView): void {
  try {
    window.localStorage.setItem(VIEW_KEY, view);
  } catch {
    // Remembering the view is optional.
  }
}

/**
 * Runs of the filtered range in four forms, switched at the top right: the timeline per
 * day, how they ended as one whole, per network, and the numbers as a table.
 */
export function RunsChart({ buckets, runs }: { buckets: ChartBucket[]; runs: RunSummary[] }) {
  const { t } = useTranslation();
  const [view, setView] = useState<ChartView>(loadView);
  const empty = buckets.every((bucket) => bucketTotal(bucket) === 0);
  const present = OUTCOMES.filter((key) => buckets.some((bucket) => bucket[key] > 0));
  // Ranges under two days count per hour.
  const titleKey = buckets[0]?.unit === 'hour' && (view === 'timeline' || view === 'table') ? `${view}Hours` : view;
  const choose = (next: ChartView) => {
    setView(next);
    saveView(next);
  };

  return (
    <Card className={cn(moduleCardClass, 'h-full min-w-0')}>
      <CardHeader className="shrink-0 pb-2">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
          <CardTitle className="truncate">{t(`history.chart.titles.${titleKey}`)}</CardTitle>
          <div
            role="radiogroup"
            aria-label={t('history.chart.viewLabel')}
            className="inline-flex h-8 shrink-0 items-stretch rounded-md border border-input p-0.5 shadow-sm"
          >
            {VIEWS.map(({ id, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={view === id}
                title={t(`history.chart.views.${id}`)}
                onClick={() => choose(id)}
                className={cn(
                  'flex items-center gap-1.5 rounded px-2 text-xs transition-colors',
                  view === id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
                )}
              >
                <Icon className="size-3.5" aria-hidden />
                <span className="hidden xl:inline">{t(`history.chart.views.${id}`)}</span>
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className={cn(moduleCardBodyClass, 'flex flex-col')}>
        {empty ? (
          <p className="text-sm text-muted-foreground">{t('history.chart.empty')}</p>
        ) : view === 'share' ? (
          <ShareView buckets={buckets} />
        ) : view === 'table' ? (
          <TableView buckets={buckets} />
        ) : (
          <>
            {view === 'networks' ? <NetworksView runs={runs} /> : <TimelineView buckets={buckets} />}
            {/* Two or more series: a legend, so identity never rests on colour alone. */}
            <ul className="mt-2 flex shrink-0 flex-wrap gap-3 text-xs">
              {present.map((key) => (
                <li key={key} className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm" style={{ background: OUTCOME_FILL[key] }} aria-hidden />
                  {t(`history.outcome.${key}`)}
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
