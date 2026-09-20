import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { moduleCardBodyClass, moduleCardClass } from '@/modules/moduleCard';

type SetupItem = {
  id: string;
  labelKey: string;
  to: string;
  actionKey: string;
};

export function SetupCard({
  loading,
  ollamaOk,
  helpConfigured,
  hasNetwork,
}: {
  loading: boolean;
  ollamaOk?: boolean;
  helpConfigured?: boolean;
  hasNetwork?: boolean;
}) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <Card className={moduleCardClass}>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  const items: SetupItem[] = [];
  if (ollamaOk === false) {
    items.push({
      id: 'ollama',
      labelKey: 'dashboard.setup.ollama',
      to: '/settings#runtime',
      actionKey: 'dashboard.setup.runtimeLink',
    });
  }
  if (helpConfigured === false) {
    items.push({
      id: 'help',
      labelKey: 'dashboard.setup.help',
      to: '/settings#help-chat',
      actionKey: 'dashboard.setup.helpLink',
    });
  }
  if (hasNetwork === false) {
    items.push({
      id: 'networks',
      labelKey: 'dashboard.setup.networks',
      to: '/network',
      actionKey: 'dashboard.setup.createNetwork',
    });
  }

  if (items.length === 0) return null;

  return (
    <Card className={moduleCardClass}>
      <CardHeader>
        <CardTitle>{t('dashboard.setup.title')}</CardTitle>
      </CardHeader>
      <CardContent className={`${moduleCardBodyClass} space-y-3`}>
        {items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p>{t(item.labelKey)}</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="outline">
                <Link to={item.to}>{t(item.actionKey)}</Link>
              </Button>
              {item.id === 'networks' ? (
                <Button asChild size="sm" variant="ghost">
                  <Link to="/networks">{t('dashboard.setup.importNetwork')}</Link>
                </Button>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
