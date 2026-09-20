import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatRelative } from '@/lib/relativeTime';
import {
  durationMs,
  formatDuration,
  outcomeBadgeVariant,
  type RunSummary,
} from '@/modules/dashboard/model';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';

export function RecentRunsCard({
  loading,
  storeOk,
  items,
}: {
  loading: boolean;
  storeOk: boolean;
  items: RunSummary[];
}) {
  const { t, i18n } = useTranslation();

  if (loading) {
    return (
      <Card className={moduleCardClass}>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={moduleCardClass}>
      <CardHeader>
        <CardTitle>{t('dashboard.runs.title')}</CardTitle>
      </CardHeader>
      <CardContent className={moduleCardBodyClass}>
        {!storeOk ? (
          <Alert>
            <AlertTitle>{t('dashboard.runs.storeError')}</AlertTitle>
            <AlertDescription>
              <Button asChild size="sm" variant="outline" className="mt-2">
                <Link to="/settings#data">{t('dashboard.runs.openData')}</Link>
              </Button>
            </AlertDescription>
          </Alert>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('dashboard.runs.empty')}</p>
        ) : (
          <ul className="space-y-1">
            {items.map((run) => {
              const href = run.outcome === 'running' ? '/monitoring' : `/history/${run.runId}`;
              return (
                <li key={run.runId}>
                  <Link
                    to={href}
                    className="flex items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-accent"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{run.networkName}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDuration(durationMs(run.startedAt, run.endedAt), t)}
                        {' · '}
                        {formatRelative(Date.parse(run.startedAt), i18n.language)}
                      </p>
                    </div>
                    <Badge variant={outcomeBadgeVariant(run.outcome)}>
                      {t(`dashboard.outcome.${run.outcome}`)}
                    </Badge>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
