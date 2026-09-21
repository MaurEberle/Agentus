import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSessionQuery } from '@/api/session';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { formatRelative } from '@/lib/relativeTime';
import { serviceBadgeVariant } from '@/modules/dashboard/model';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';
import { useAppStore } from '@/store';

export function StatusCard() {
  const { t, i18n } = useTranslation();
  const serviceStatus = useAppStore((state) => state.serviceStatus);
  const phase = useAppStore((state) => state.phase);
  const phaseLabel = useAppStore((state) => state.phaseLabel);
  const activeNetworkId = useAppStore((state) => state.activeNetworkId);
  const activeNetworkName = useAppStore((state) => state.activeNetworkName);
  const { data: session, isLoading } = useSessionQuery();
  const startedAt = session?.startedAt;
  const live = serviceStatus === 'running' || serviceStatus === 'starting';

  return (
    <Card className={moduleCardClass}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>{t('dashboard.status.title')}</CardTitle>
        {isLoading ? (
          <Skeleton className="h-5 w-20" />
        ) : (
          <Badge variant={serviceBadgeVariant(serviceStatus)}>{t(`status.${serviceStatus}`)}</Badge>
        )}
      </CardHeader>
      <CardContent className={`${moduleCardBodyClass} flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`}>
        <div className="space-y-1 text-sm">
          {activeNetworkId ? (
            <p className="font-medium">{activeNetworkName ?? activeNetworkId}</p>
          ) : (
            <p className="text-muted-foreground">{t('dashboard.status.noNetwork')}</p>
          )}
          {serviceStatus === 'starting' && phase === 'index' && phaseLabel ? (
            <p className="text-muted-foreground">{t('dashboard.status.indexing', { name: phaseLabel })}</p>
          ) : null}
          {live && startedAt ? (
            <p className="text-muted-foreground">
              {t('dashboard.status.runningSince', {
                time: formatRelative(Date.parse(startedAt), i18n.language),
              })}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {!activeNetworkId ? (
            <Button asChild variant="outline" size="sm">
              <Link to="/networks">{t('dashboard.status.openLibrary')}</Link>
            </Button>
          ) : null}
          {live ? (
            <Button asChild size="sm">
              <Link to="/monitoring">{t('dashboard.status.openMonitoring')}</Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
