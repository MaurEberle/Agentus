import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDuration, formatInt, formatPercent } from '@/modules/history/model/format';
import type { HistoryKpis } from '@/modules/history/model/types';

export function KpiRow({ kpis, loading }: { kpis: HistoryKpis; loading: boolean }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  if (loading) {
    return (
      <div className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  const pct = (value: number) => (kpis.total === 0 ? '—' : formatPercent((value / kpis.total) * 100, locale));

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Tile title={t('history.kpi.runs')} value={formatInt(kpis.total, locale)} hint={t('history.kpi.runsHint')} />
      <Tile
        title={t('history.kpi.succeeded')}
        value={`${formatInt(kpis.succeeded, locale)} · ${pct(kpis.succeeded)}`}
      />
      <Tile
        title={t('history.kpi.failed')}
        value={`${formatInt(kpis.failed, locale)} · ${pct(kpis.failed)}`}
        hint={t('history.kpi.failedFoot', { cancelled: kpis.cancelled, timeout: kpis.timeout })}
      />
      <Tile
        title={t('history.kpi.medianDuration')}
        value={kpis.medianMs === null ? '—' : formatDuration(kpis.medianMs)}
        hint={
          kpis.p95Ms !== null
            ? t('history.kpi.p95', { value: formatDuration(kpis.p95Ms) })
            : t('history.kpi.p95Hidden')
        }
      />
    </div>
  );
}

function Tile({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <Card className="h-full min-w-0">
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xl font-semibold tabular-nums">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
