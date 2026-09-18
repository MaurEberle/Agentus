import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { countWeekStats, type RunSummary } from '@/modules/dashboard/model';

export function WeekStatsCard({
  loading,
  storeOk,
  items,
}: {
  loading: boolean;
  storeOk: boolean;
  items: RunSummary[];
}) {
  const { t } = useTranslation();
  const stats = storeOk ? countWeekStats(items) : { runs: 0, succeeded: 0, failed: 0 };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-36" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>{t('dashboard.week.title')}</CardTitle>
        <Button asChild size="sm" variant="ghost">
          <Link to="/history">{t('dashboard.week.openHistory')}</Link>
        </Button>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-3 gap-2 text-center">
          <div>
            <dt className="text-xs text-muted-foreground">{t('dashboard.week.runs')}</dt>
            <dd className="text-2xl font-semibold tabular-nums">{stats.runs}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">{t('dashboard.week.succeeded')}</dt>
            <dd className="text-2xl font-semibold tabular-nums">{stats.succeeded}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">{t('dashboard.week.failed')}</dt>
            <dd className="text-2xl font-semibold tabular-nums">{stats.failed}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
