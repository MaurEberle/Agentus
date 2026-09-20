import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { failingStores } from '@/modules/dashboard/model';
import type { HelpChatStatus } from '@/components/help-chat/model';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';
import type { DataLocation, RuntimeModel, RuntimePing } from '@/modules/settings/model';

export function EnvironmentCard({
  loading,
  ping,
  models,
  stores,
  help,
}: {
  loading: boolean;
  ping?: RuntimePing;
  models: RuntimeModel[];
  stores?: DataLocation;
  help?: HelpChatStatus;
}) {
  const { t } = useTranslation();
  const broken = failingStores(stores);

  if (loading) {
    return (
      <Card className={moduleCardClass}>
        <CardHeader>
          <Skeleton className="h-4 w-28" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={moduleCardClass}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>{t('dashboard.environment.title')}</CardTitle>
        {help?.degraded ? <Badge variant="warning">{t('dashboard.environment.degraded')}</Badge> : null}
      </CardHeader>
      <CardContent className={`${moduleCardBodyClass} space-y-2 text-sm`}>
        <p className={ping?.ok ? 'text-foreground' : 'text-destructive'}>
          {ping?.ok ? t('dashboard.environment.ollamaOk') : t('dashboard.environment.ollamaFail')}
        </p>
        {models.length > 0 ? (
          <p className="text-muted-foreground">
            {t('dashboard.environment.models', { count: models.length })}
          </p>
        ) : null}
        {broken.map((store) => (
          <div key={store.id} className="flex items-center justify-between gap-2">
            <p className="text-destructive">
              {t('dashboard.environment.storeIssue', {
                store: t(`settings.data.store.${store.id}`),
              })}
            </p>
            <Button asChild size="sm" variant="outline">
              <Link to="/settings#data">{t('dashboard.environment.openData')}</Link>
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
